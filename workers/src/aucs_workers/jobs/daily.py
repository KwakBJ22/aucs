"""아침 묶음 (10/18 대표님, 11/4 저녁: 사건 서류·사진·다음 회차는 매시 작업 court_hourly 로 옮김 — 하루 종일 나눠 받기): 매각결과 → 물건 수집 → 건축물대장(10/27) → 공시가격(11/11) → 공매(10/28) → 분석 → 첫 화면 숫자 새로(11/4) → 알림 → 지우기.

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
    ("낙찰 순간 기록", ["aucs_workers.jobs.sale_snapshot"]),  # 11/21 — 입찰 전 분석을 얼려 둠(요인표)
    ("물건 수집", ["aucs_workers.collectors.court_items"]),
    ("건축물대장", ["aucs_workers.collectors.buildings"]),
    ("건축물대장 호", ["aucs_workers.collectors.units"]),  # 11/16 — 전유 용도 · 면적
    ("공시가격", ["aucs_workers.collectors.official_prices", "--cap", "1500"]),  # 11/11 — 재산세·종부세 바탕
    ("토지이용계획", ["aucs_workers.collectors.land_use", "--cap", "3000"]),  # 11/14 — 정비구역 안인지
    ("상가 주변 가게", ["aucs_workers.collectors.stores"]),  # 11/16 — 반경 300m 업종
    ("공매", ["aucs_workers.collectors.onbid"]),
    # 11/24 대표님 「빠뜨리지 않게」: 아침 분석은 날마다 전체(약 20분) — 물건이 그대로여도 새 실거래 · 새 낙찰 사례가
    #   예상 낙찰가 · 주변 시세에 그날 들어가게(전엔 월요일만 전체라 최대 일주일 늦었음). 낮에는 매시 --stale 그대로
    ("분석(전체)", ["aucs_workers.jobs.analyze"]),
    ("첫 화면 숫자 새로", ["aucs_workers.jobs.warm"]),
    ("알림", ["aucs_workers.jobs.notify"]),
    ("올린 등기부 원본 지우기", ["aucs_workers.jobs.purge"]),
    # 11/18 전국 매각결과 · 물건 목록 보관 → 11/23 대표님: 아침에 몰려 법원이 막음 → 오후 매시 작업(court_hourly)으로 옮김
    # 11/20 대표님: 건축물대장 호가 입찰 3~4일 전에야 붙음(7,250건 중 1,518건) → 아침 1,200건 뒤에 밀린 것을 3,000건 더.
    # 맨 뒤라 분석이 늦어지지 않고, 받은 물건은 매시 분석(--stale)이 다시 봄. 공공데이터 하루 한도에 닿으면 받은 데까지 저장하고 멈춤.
    ("건축물대장 호(밀린 것)", ["aucs_workers.collectors.units", "--cap", "3000"]),
]


def steps_for(today: date) -> list[tuple[str, list[str]]]:
    """아침 묶음 단계(11/24 — 날마다 같음. 전엔 월요일만 분석이 전체였음)."""
    return STEPS


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
