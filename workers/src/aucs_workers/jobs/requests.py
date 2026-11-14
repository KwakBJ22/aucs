"""관리자 「다시 돌리기 요청」 처리(11/2): 작업 스케줄러가 5분마다 부름.

기다리는 요청을 오래된 것부터 하나씩 실행(run-job.ps1 과 같은 작업). 할 일이 없으면 바로 끝남.
도는 요청이 있으면(6시간 안) 새로 시작하지 않음.

    uv run python -m aucs_workers.jobs.requests
"""

import subprocess
import sys
from datetime import datetime
from pathlib import Path

from aucs_workers.db import connect

ROOT = Path(__file__).resolve().parents[4]
RUN_JOB = ROOT / "scripts" / "run-job.ps1"
NIGHT_END = 6  # 이 시각 전에는 손님 서류 요청도 법원에 묻지 않음
KEYS = {"daily", "results", "items", "docs", "analyze", "notify", "buildings", "onbid", "trades",
        "redev", "watched", "regions"}  # fmt: skip


def command(key: str) -> list[str] | None:
    """요청 이름 → 실행할 명령. 모르는 이름은 None."""
    if key.startswith("analyze_item:"):
        return [sys.executable, "-m", "aucs_workers.jobs.analyze", "--item", key.split(":", 1)[1]]
    if key in KEYS:
        return [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(RUN_JOB),
            key,
        ]
    return None


def queue_docs() -> None:
    """손님이 연 물건의 서류 요청(case_docs:, 11/4)을 한 번에 받고, 바뀐 물건만 다시 분석. 실패해도 관리자 요청은 계속.

    11/11 대표님: 밤(00~06시)에는 법원에 묻지 않음 — 요청은 줄에 남아 있다가 06시 뒤 첫 차례에 받음."""
    if datetime.now().hour < NIGHT_END:
        return
    with connect() as c:
        if c.execute(  # 앞 차례가 아직 받는 중이면 겹쳐 띄우지 않음(법원에 한 번에 한 창만)
            "select 1 from ops.job_requests where status = 'running' and job_key like 'case_docs:%%'"
            " and started_at > now() - interval '30 minutes'"
        ).fetchone():
            return
        n = c.execute(
            "select count(*) from ops.job_requests where status = 'waiting' and job_key like 'case_docs:%%'"
        ).fetchone()
    if not n or not n[0]:
        return
    print(f"── 손님이 연 물건 서류 {n[0]}건", flush=True)
    if (
        subprocess.call(
            [sys.executable, "-m", "aucs_workers.collectors.court_docs", "--queue"], cwd=ROOT
        )
        == 0
    ):
        subprocess.call([sys.executable, "-m", "aucs_workers.jobs.analyze", "--stale"], cwd=ROOT)


def main() -> None:
    try:  # Vercel 이 남긴 그림 등기부부터(11/3) — 실패해도 요청 처리는 계속
        from aucs_workers.jobs import registry_ocr

        registry_ocr.main()
    except Exception as e:  # noqa: BLE001
        print(f"등기부 글자 인식 실패: {e}", flush=True)
    try:  # 손님이 올린 그림 감정평가서(11/14) — 사건번호가 맞으면 바로 넣음
        from aucs_workers.jobs import appraisal_ocr

        appraisal_ocr.main()
    except Exception as e:  # noqa: BLE001
        print(f"감정평가서 글자 인식 실패: {e}", flush=True)
    try:  # 대표님이 받아 둔 감정평가서 폴더(11/14) — 새 PDF 가 있으면 넣고 「넣음」·「못 넣음」으로 옮김
        from aucs_workers.collectors import appraisal_folder

        if got := appraisal_folder.inbox():
            print(f"── 감정평가서 받은 폴더: {got}", flush=True)
    except Exception as e:  # noqa: BLE001
        print(f"감정평가서 받은 폴더 실패: {e}", flush=True)
    queue_docs()
    try:  # 빨간 불 휴대폰 알림 · 관리자가 쓴 알림 보내기(11/12) — 실패해도 요청 처리는 계속
        from aucs_workers import ops_watch

        print(ops_watch.run_once(), flush=True)
    except Exception as e:  # noqa: BLE001
        print(f"운영 알림 실패: {e}", flush=True)
    with connect() as c:
        busy = c.execute(
            "select 1 from ops.job_requests where status = 'running' and started_at > now() - interval '6 hours'"
        ).fetchone()
        if busy:
            return
        c.execute(
            """update ops.job_requests set status = 'failed', finished_at = now(), message = '6시간 넘게 안 끝남'
               where status = 'running'"""
        )
        row = c.execute(
            """update ops.job_requests set status = 'running', started_at = now()
               where req_id = (select req_id from ops.job_requests where status = 'waiting'
                               and job_key not like 'case_docs:%%'
                               order by requested_at limit 1 for update skip locked)
               returning req_id, job_key"""
        ).fetchone()
        c.commit()
    if not row:
        return
    req_id, key = row
    cmd = command(key)
    if cmd is None:
        code, msg = 1, "모르는 작업"
    else:
        print(f"── 요청 {req_id}: {key}", flush=True)
        code = subprocess.call(cmd, cwd=ROOT)
        msg = "끝" if code == 0 else f"끝 코드 {code} · logs 확인"
    with connect() as c:
        c.execute(
            "update ops.job_requests set status = %s, finished_at = now(), message = %s where req_id = %s",
            ("done" if code == 0 else "failed", msg, req_id),
        )
        c.commit()


if __name__ == "__main__":
    main()
