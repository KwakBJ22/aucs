"""낙찰가율 분포와 예상 낙찰가 범위.

같은 시군구·용도·면적대·유찰횟수, 최근 12개월의 25%·중앙·75% 지점.
표본 10건 미만이면 시도로 넓히고 「표본 적음」. 특수 사건은 기본값에서 뺍니다.
"""

from dataclasses import dataclass
from datetime import date, timedelta

from aucs_rules.result import RuleResult, Status

MIN_SAMPLE = 10


@dataclass(frozen=True)
class Sale:
    sale_date: date
    sido: str | None
    sigungu: str | None
    usage_name: str | None
    area_m2: float | None
    failed_count: int | None
    sale_rate: float  # 낙찰가/감정가 %
    is_special_case: bool = False


def area_band(area: float | None) -> str:
    if area is None:
        return "모름"
    for upper, name in [(40, "~40"), (60, "40~60"), (85, "60~85"), (135, "85~135")]:
        if area < upper:
            return name
    return "135~"


def _quantile(xs: list[float], q: float) -> float:
    s = sorted(xs)
    pos = (len(s) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(s) - 1)
    return round(s[lo] + (s[hi] - s[lo]) * (pos - lo), 1)


def rate_range(
    sales: list[Sale],
    *,
    as_of: date,
    sido: str | None,
    sigungu: str | None,
    usage_name: str | None,
    area_m2: float | None,
    failed_count: int | None,
    include_special: bool = False,
) -> RuleResult:
    """기준일(as_of)부터 12개월 안의 매각 사례로 범위를 냅니다.

    표본이 10건 미만이면 차례로 넓힙니다: 시군구 → 시도 → 유찰횟수 빼기 → 면적대 빼기.
    넓힌 단계는 결과의 relaxed 에 남깁니다(화면에 「표본 적음」·「넓혀 계산」 표시).
    """
    since = as_of - timedelta(days=365)
    band = area_band(area_m2)
    pool0 = [
        s for s in sales
        if since <= s.sale_date <= as_of and s.usage_name == usage_name
        and (include_special or not s.is_special_case)
    ]  # fmt: skip
    steps: list[tuple[str, list[str], list[Sale]]] = []
    same_band = [s for s in pool0 if area_band(s.area_m2) == band]
    same_fail = [s for s in same_band if (s.failed_count or 0) == (failed_count or 0)]
    steps.append(("sigungu", [], [s for s in same_fail if s.sigungu == sigungu]))
    steps.append(("sido", [], [s for s in same_fail if s.sido == sido]))
    steps.append(("sido", ["failed_count"], [s for s in same_band if s.sido == sido]))
    steps.append(("sido", ["failed_count", "area"], [s for s in pool0 if s.sido == sido]))
    scope, relaxed, pool = steps[-1]
    for step in steps:
        if len(step[2]) >= MIN_SAMPLE:
            scope, relaxed, pool = step
            break
    rates = [s.sale_rate for s in pool]
    if not rates:
        return RuleResult(None, Status.UNKNOWN, "sale_rate.none", [{"scope": scope}])
    value = {
        "p25": _quantile(rates, 0.25),
        "p50": _quantile(rates, 0.5),
        "p75": _quantile(rates, 0.75),
        "n": len(rates),
        "scope": scope,
        "relaxed": relaxed,
        "small_sample": len(rates) < MIN_SAMPLE,
    }
    return RuleResult(value, Status.ESTIMATED, "sale_rate.range", [{"band": band}])


def expected_price_range(market_price_krw: int | None, rates: RuleResult) -> RuleResult:
    """예상 낙찰가 = 시세 × 낙찰가율 구간. 하나의 숫자가 아니라 범위."""
    if market_price_krw is None or rates.value is None:
        return RuleResult(None, Status.UNKNOWN, "sale_rate.price.none", [])
    v = rates.value
    lo, hi = market_price_krw * v["p25"] / 100, market_price_krw * v["p75"] / 100
    return RuleResult((int(lo), int(hi)), Status.ESTIMATED, "sale_rate.price", [v])


def next_round_min_price(min_price_krw: int, reduction_pct: float | None) -> RuleResult:
    """유찰 시 다음 최저가 = 현재 최저가 × (1 − 저감률). 저감률 모르면 「정보부족」."""
    if reduction_pct is None:
        return RuleResult(None, Status.UNKNOWN, "round.next.no_rate", [{"note": "정보부족"}])
    return RuleResult(
        round(min_price_krw * (100 - reduction_pct) / 100), Status.ESTIMATED, "round.next", []
    )
