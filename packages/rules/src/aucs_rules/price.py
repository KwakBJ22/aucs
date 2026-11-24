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


NEARBY_MIN = 5  # 주변 비슷한 집 — 이보다 적으면 내지 않음
NEARBY_MIN_LOTS = 2  # 한 건물 거래만으로 「주변」이라 하지 않음


def _q(xs: list[float], p: float) -> float:
    """정렬된 값의 p 지점(선형 보간)."""
    k = (len(xs) - 1) * p
    lo = int(k)
    hi = min(lo + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def nearby_price(
    trades: list[Trade],
    *,
    as_of: date,
    area_m2: float,
    build_year: int | None = None,
) -> RuleResult:
    """같은 법정동 · 같은 종류 · 전용 ±10% · 지은 해 ±5년 · 최근 12개월 매매의 ㎡단가로 이 넓이 값을 어림.

    같은 건물 거래가 적을 때(1년 3건 미만) 보여 주는 배경 정보 — 입찰가 계산에는 쓰지 않음(11/24 대표님 ①).
    튀는 거래는 빼고(_drop_outliers) 25 · 50 · 75% 지점을 냄. 빌라는 건물마다 값 차이가 커서 범위를 같이 보임.
    """
    since = as_of - timedelta(days=365)
    pool = [
        t for t in trades
        if not t.cancelled and since <= t.deal_date <= as_of and t.area_m2 > 0
        and abs(t.area_m2 - area_m2) <= area_m2 * 0.1
        and (build_year is None or t.build_year is None or abs(t.build_year - build_year) <= 5)
    ]  # fmt: skip
    used = _drop_outliers(pool)
    lots = {t.complex_name for t in used if t.complex_name}
    if len(used) < NEARBY_MIN or len(lots) < NEARBY_MIN_LOTS:
        return RuleResult(None, Status.UNKNOWN, "price.nearby.few", [{"n": len(used)}])
    ppm = sorted(t.price_krw / t.area_m2 for t in used)
    value = {
        "n": len(used),
        "lots": len(lots),
        "p25_krw": int(_q(ppm, 0.25) * area_m2),
        "p50_krw": int(_q(ppm, 0.5) * area_m2),
        "p75_krw": int(_q(ppm, 0.75) * area_m2),
        "area_m2": area_m2,
        "build_year": build_year,
    }
    return RuleResult(value, Status.ESTIMATED, "price.nearby", [])


def trade_region(code: str) -> str:
    """실거래 자료는 법정동을 읍·면까지만 씀(리 코드 끝 두 자리가 00). 리 주소 물건도 맞게(10/28)."""
    return code[:8] + "00" if len(code) == 10 else code
