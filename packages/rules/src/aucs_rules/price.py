"""시세: 비교 거래 고르기와 기준값 (04탭 4절).

1 같은 단지·전용 ±3㎡·12개월 (3건 이상) → 2 같은 단지·같은 면적·24개월 → 3 반경 500m·연식 ±5년·면적 ±10%.
같은 법정동 ㎡단가는 배경 정보로만(입찰가 계산에 쓰지 않음).
"""

from dataclasses import dataclass
from datetime import date, timedelta
from statistics import median

from aucs_rules.result import RuleResult, Status


@dataclass(frozen=True)
class Trade:
    deal_date: date
    price_krw: int
    area_m2: float
    floor: int | None
    complex_name: str | None
    build_year: int | None = None
    distance_m: float | None = None  # 대상 물건에서의 거리
    cancelled: bool = False


def _drop_outliers(trades: list[Trade]) -> list[Trade]:
    """사분위 범위(IQR) 밖 극단값 제외. 4건 미만이면 그대로."""
    if len(trades) < 4:
        return trades
    ppm = sorted(t.price_krw / t.area_m2 for t in trades)
    n = len(ppm)
    q1, q3 = ppm[n // 4], ppm[(3 * n) // 4]
    lo, hi = q1 - 1.5 * (q3 - q1), q3 + 1.5 * (q3 - q1)
    return [t for t in trades if lo <= t.price_krw / t.area_m2 <= hi]


def market_price(
    trades: list[Trade],
    *,
    as_of: date,
    complex_name: str | None,
    area_m2: float,
    build_year: int | None = None,
) -> RuleResult:
    """기준 시세(원)와 쓴 거래 목록."""
    live = [t for t in trades if not t.cancelled and t.deal_date <= as_of]
    same = [
        t
        for t in live
        if complex_name and t.complex_name == complex_name and abs(t.area_m2 - area_m2) <= 3
    ]
    lv1 = [t for t in same if t.deal_date >= as_of - timedelta(days=365)]
    lv2 = [t for t in same if t.deal_date >= as_of - timedelta(days=730)]
    lv3 = [
        t for t in live
        if t.distance_m is not None and t.distance_m <= 500 and abs(t.area_m2 - area_m2) <= area_m2 * 0.1
        and (build_year is None or t.build_year is None or abs(t.build_year - build_year) <= 5)
        and t.deal_date >= as_of - timedelta(days=365)
    ]  # fmt: skip
    for level, pool, need, status in [
        (1, lv1, 3, Status.ESTIMATED),
        (2, lv2, 1, Status.ESTIMATED),
        (3, lv3, 1, Status.ESTIMATED),
    ]:
        used = _drop_outliers(pool)
        if len(used) >= need:
            ppm = median(t.price_krw / t.area_m2 for t in used)
            value = {"price_krw": int(ppm * area_m2), "level": level, "n": len(used)}
            ev = [
                {"date": str(t.deal_date), "floor": t.floor, "price_krw": t.price_krw} for t in used
            ]
            return RuleResult(value, status, f"price.level{level}", ev)
    return RuleResult(None, Status.UNKNOWN, "price.none", [])


def trade_region(code: str) -> str:
    """실거래 자료는 법정동을 읍·면까지만 씀(리 코드 끝 두 자리가 00). 리 주소 물건도 맞게(10/28)."""
    return code[:8] + "00" if len(code) == 10 else code
