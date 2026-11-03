"""아침 묶음 (10/18 대표님): 매각결과 → 물건 수집 → 건축물대장(10/27) → 공매(10/28) → 바로 분석 → 서류 보관 → 받은 물건 다시 분석 → 첫 화면 숫자 새로(11/4) → 알림.

작업 스케줄러가 매일 07:00에 부르고, PC가 꺼져 있었으면 켜지는 순간 시작합니다(StartWhenAvailable).
순서가 섞이지 않도록 한 작업 안에서 차례로 돌립니다. 한 단계가 실패해도 다음 단계는 계속하고,
마지막에 실패가 있었으면 0이 아닌 값으로 끝나 알림창이 뜹니다.

    uv run python -m aucs_workers.jobs.daily
"""

import subprocess
import sys
from datetime import date

STEPS = [
    ("매각결과", ["aucs_workers.collectors.court_results"]),
    ("물건 수집", ["aucs_workers.collectors.court_items"]),
    ("건축물대장", ["aucs_workers.collectors.buildings"]),
    ("공매", ["aucs_workers.collectors.onbid"]),
    ("분석(새 물건)", ["aucs_workers.jobs.analyze", "--stale"]),
    ("서류 보관", ["aucs_workers.collectors.court_docs", "--archive"]),
    ("분석(새 서류)", ["aucs_workers.jobs.analyze", "--stale"]),
    ("첫 화면 숫자 새로", ["aucs_workers.jobs.warm"]),
    ("알림", ["aucs_workers.jobs.notify"]),
    ("올린 등기부 원본 지우기", ["aucs_workers.jobs.purge"]),
]


def steps_for(today: date) -> list[tuple[str, list[str]]]:
    """월요일에는 마지막 분석을 전체로(낙찰 사례가 쌓여 범위가 바뀌므로)."""
    if today.weekday() != 0:
        return STEPS
    return [(n, ["aucs_workers.jobs.analyze"] if n == "분석(새 서류)" else m) for n, m in STEPS]


def main() -> None:
    failed = []
    for name, mod in steps_for(date.today()):
        print(f"── {name}", flush=True)
        code = subprocess.call([sys.executable, "-m", *mod])
        if code != 0:
            failed.append(name)
            print(f"   {name} 실패({code}) — 다음 단계는 계속", flush=True)
    print("끝" + (f" · 실패: {', '.join(failed)}" if failed else ""), flush=True)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
