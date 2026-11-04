"""관심 담으면 바로 준비(16): 낮 동안 매시, 관심에 담은 뒤 아직 안 받은 서류·건축물대장을 받고 다시 분석.

할 일이 없으면 몇 초 만에 끝납니다(법원 사이트에 들어가지 않음).

    uv run python -m aucs_workers.jobs.watched
"""

import subprocess
import sys

STEPS = [
    # 관심 물건 서류는 매시 법원 작업(court_hourly)이 맨 먼저 받음(11/4 — 법원에 두 창이 겹치지 않게)
    ("건축물대장(관심 먼저)", ["aucs_workers.collectors.buildings", "--cap", "60"]),
    ("분석", ["aucs_workers.jobs.analyze", "--stale"]),
]


def main() -> None:
    failed = []
    for name, mod in STEPS:
        print(f"── {name}", flush=True)
        if subprocess.call([sys.executable, "-m", *mod]) != 0:
            failed.append(name)
    print("끝" + (f" · 실패: {', '.join(failed)}" if failed else ""), flush=True)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
