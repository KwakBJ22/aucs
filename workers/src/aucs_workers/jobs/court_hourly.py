"""법원 수집 매시(11/4 저녁 대표님 — 하루 종일 나눠 계속 받기, PC 는 웬만하면 켜 둠).

작업 스케줄러가 매시 10분에 부르고, PC 가 꺼져 있다 켜지면 바로 한 번 돕니다(StartWhenAvailable).
법원 서비스 시간(06~24시)에만 돌고, 시간마다 몫(하루 한도 ÷ 18, polite.py)을 다 쓰면 그 단계는 멈추고 다음 시간에 이어 받습니다.
받는 순서(손님 눈에 먼저 띄는 것부터): 관심 물건 → 추천 후보 사진 → 다음 회차 미리 → 서류 보관 → 감정평가서 원본 → 분석.
앞 차례가 아직 돌고 있으면(70분 안) 겹쳐 띄우지 않습니다.

    uv run python -m aucs_workers.jobs.court_hourly
"""

import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

LOCK = Path(__file__).resolve().parents[4] / "logs" / "court_hourly.lock"
SERVICE = range(6, 24)  # 법원 06:00~24:00 (00~01시도 열리지만 하루 몫을 나누는 18시간에 맞춤)
STEPS = [
    ("관심 물건 서류", ["aucs_workers.collectors.court_docs", "--watched"]),
    ("추천 후보 사진", ["aucs_workers.collectors.court_docs", "--picks"]),
    ("다음 회차 미리 받기", ["aucs_workers.collectors.court_docs", "--next"]),
    ("서류 보관", ["aucs_workers.collectors.court_docs", "--archive"]),
    ("감정평가서 원본", ["aucs_workers.collectors.kapa_pdf"]),
    ("분석(새 서류)", ["aucs_workers.jobs.analyze", "--stale"]),
]


def busy() -> bool:
    """앞 차례가 70분 안에 시작해 아직 안 끝났으면 True."""
    return LOCK.exists() and time.time() - LOCK.stat().st_mtime < 70 * 60


def main() -> None:
    if datetime.now().hour not in SERVICE:
        print("법원 서비스 시간이 아니에요 — 쉼")
        return
    if busy():
        print("앞 차례가 아직 도는 중 — 겹쳐 띄우지 않음")
        return
    LOCK.parent.mkdir(exist_ok=True)
    LOCK.write_text(str(os.getpid()), encoding="utf-8")
    try:
        for name, mod in STEPS:
            print(f"── {name}", flush=True)
            code = subprocess.call([sys.executable, "-m", *mod])
            if code != 0:
                print(f"   {name} 멈춤({code}) — 한도·막힘이면 다음 시간에 이어서", flush=True)
    finally:
        LOCK.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
