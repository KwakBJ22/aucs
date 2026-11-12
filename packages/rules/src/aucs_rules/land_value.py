"""땅값 역산 추정 시세(LAND-01, 11/12 대표님 「상하단 넣어」).

단독·다가구·다중주택은 같은 건물 거래가 거의 없어 같은 단지 실거래(price.py)로는 시세가 비는 일이 많다.
그래서 땅과 건물을 나눠 센다.

1) 땅: 같은 법정동 단독·다가구 매매(국토부 실거래, 최근 N개월)마다
       (거래 금액 − 그 건물의 원가) ÷ 대지 면적 = 대지 ㎡당 땅값.
       극단값(사분위 범위 밖)을 빼고 p25 · p50 · p75.
       물건과 지은 해가 ±10년 안인 거래가 충분하면 그것만 씀(신축·구옥은 땅값 역산이 다르게 나옴).
2) 건물: 원가법 — ㎡당 새로 짓는 값 × 연면적 × 남은 가치 비율(1 − 지난 해 ÷ 내용연수, 바닥 있음).
       ㎡당 값 · 내용연수 · 바닥은 기준표 `land_value` 에서 읽음(감정평가실무 원가법, 한국부동산원 건물신축단가표 참고).
3) 추정 시세 = 대지 면적 × 땅값(p25 / p50 / p75) + 건물 원가 → 하단 · 가운데 · 상단.
같은 동 법원 감정(토지 감정가 ÷ 대지)은 맞춰 보기용으로만 함께 돌려줌.

순수 함수 — DB·네트워크·현재 시각을 쓰지 않음(기준일은 인자).
"""

from dataclasses import dataclass
from datetime import date, timedelta
from statistics import median
from typing import Any

from aucs_rules.result import RuleResult, Status

RULE_ID = "LAND-01"


@dataclass(frozen=True)
class HouseTrade:
    deal_date: date
    price_krw: int
    floor_area_m2: float  # 연면적
    land_m2: float  # 대지 면적
    build_year: int | None


def building_cost(
    floor_area_m2: float, build_year: int | None, as_of: date, table: dict[str, Any]
) -> int:
    """건물 원가(원가법): ㎡당 값 × 연면적 × 남은 가치 비율. 지은 해를 모르면 바닥 비율로 셈(보수적으로)."""
    per = float(table.get("building_per_m2") or 0)
    life = float(table.get("life_years") or 50)
    floor = float(table.get("min_residual") or 0.2)
    if per <= 0 or floor_area_m2 <= 0:
        return 0
    if build_year is None:
        left = floor
    else:
        age = max(0, as_of.year - build_year)
        left = max(floor, 1 - age / life)
    return int(per * floor_area_m2 * left)


def _quartiles(xs: list[float]) -> tuple[float, float, float]:
    s = sorted(xs)
    n = len(s)
    return s[n // 4], median(s), s[min(n - 1, (3 * n) // 4)]


def _drop_outliers(xs: list[float]) -> list[float]:
    """사분위 범위(IQR) 밖 극단값 제외. 4건 미만이면 그대로."""
    if len(xs) < 4:
        return xs
    q1, _, q3 = _quartiles(xs)
    lo, hi = q1 - 1.5 * (q3 - q1), q3 + 1.5 * (q3 - q1)
    return [x for x in xs if lo <= x <= hi]


def land_value(
    *,
    land_m2: float | None,
    floor_area_m2: float | None,
    build_year: int | None,
    trades: list[HouseTrade],
    court_units: list[float],
    as_of: date,
    table: dict[str, Any] | None,
) -> RuleResult:
    """대지 · 연면적 · 지은 해 + 같은 동 거래 → 추정 시세 하단 · 가운데 · 상단."""
    if not table or not land_m2 or land_m2 <= 0 or not floor_area_m2:
        return RuleResult(None, Status.UNKNOWN, RULE_ID, [])
    months = int(table.get("months") or 24)
    need = int(table.get("min_n") or 5)
    start = as_of - timedelta(days=round(months * 30.4))
    live = [
        t for t in trades
        if start <= t.deal_date <= as_of
        and t.land_m2 > 0 and t.floor_area_m2 > 0 and t.price_krw > 0
    ]  # fmt: skip
    if build_year is not None:
        near = [t for t in live if t.build_year is not None and abs(t.build_year - build_year) <= 10]
        if len(near) >= need:
            live = near
    units = []
    for t in live:
        land_part = t.price_krw - building_cost(t.floor_area_m2, t.build_year, t.deal_date, table)
        if land_part > 0:
            units.append(land_part / t.land_m2)
    units = _drop_outliers(units)
    if len(units) < need:
        return RuleResult(None, Status.UNKNOWN, RULE_ID, [{"trades": len(units), "need": need}])
    p25, p50, p75 = _quartiles(units)
    bldg = building_cost(floor_area_m2, build_year, as_of, table)
    court = _drop_outliers([u for u in court_units if u > 0])
    value = {
        "low_krw": int(land_m2 * p25 + bldg),
        "mid_krw": int(land_m2 * p50 + bldg),
        "high_krw": int(land_m2 * p75 + bldg),
        "land_unit": {"p25": int(p25), "p50": int(p50), "p75": int(p75)},
        "land_m2": round(land_m2, 2),
        "building_krw": bldg,
        "n": len(units),
        "court_n": len(court),
        "court_unit": int(median(court)) if len(court) >= 3 else None,
    }
    ev = [{"source": "국토부 실거래 단독·다가구", "months": months, "n": len(units),
           "building_per_m2": table.get("building_per_m2"), "life_years": table.get("life_years")}]  # fmt: skip
    return RuleResult(value, Status.ESTIMATED, RULE_ID, ev)
