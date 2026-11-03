"""관리자 「다시 돌리기 요청」 처리(11/2): 작업 스케줄러가 5분마다 부름.

기다리는 요청을 오래된 것부터 하나씩 실행(run-job.ps1 과 같은 작업). 할 일이 없으면 바로 끝남.
도는 요청이 있으면(6시간 안) 새로 시작하지 않음.

    uv run python -m aucs_workers.jobs.requests
"""

import subprocess
import sys
from pathlib import Path

from aucs_workers.db import connect

ROOT = Path(__file__).resolve().parents[4]
RUN_JOB = ROOT / "scripts" / "run-job.ps1"
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


def main() -> None:
    try:  # Vercel 이 남긴 그림 등기부부터(11/3) — 실패해도 요청 처리는 계속
        from aucs_workers.jobs import registry_ocr

        registry_ocr.main()
    except Exception as e:  # noqa: BLE001
        print(f"등기부 글자 인식 실패: {e}", flush=True)
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
