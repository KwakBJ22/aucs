"""낙찰가율 분포와 예상 낙찰가 범위.

같은 시군구·용도·면적대·유찰횟수, 최근 12개월의 25%·중앙·75% 지점.
표본 10건 미만이면 시도로 넓히고 「표본 적음」. 특수 사건은 기본값에서 뺍니다.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

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
    court_code: str | None = None
    min_rate: float | None = None  # 그 회차 최저가/감정가 %


def _in_trim(s: Sale) -> bool:
    """낙찰가율이 [최저가율, 200%] 밖이면 뺍니다(한 건의 664% 낙찰이 분포를 무너뜨린 사례)."""
    lo = s.min_rate if s.min_rate is not None else 0.0
    return lo <= s.sale_rate <= 200


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
        and (include_special or not s.is_special_case) and _in_trim(s)
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


def adjusted_rates(
    rate: dict[str, Any] | None,
    court: dict[str, Any] | None,
    appraisal_krw: int | None,
    min_price_krw: int | None,
) -> dict[str, Any] | None:
    """예상 낙찰가율(감정가 대비 %) 한 곳(11/8 — 상세 「얼마짜리인가」와 추천·모아 보기가 같은 값).
    비슷한 물건 25·50·75% 지점 → 관할 법원 칸이 기준이면 그 차이만큼 옮김 → 최저가 아래로는 안 내려감.
    값: lo·mid·hi(%) · shift(법원으로 옮긴 %p) · below(비슷한 물건이 이번 최저가보다 싸게 팔렸는지)."""
    if not rate or rate.get("p50") is None:
        return None
    mid = float(rate["p50"])
    lo, hi = float(rate.get("p25", mid)), float(rate.get("p75", mid))
    shift = 0.0
    if court and court.get("use_as_base"):
        shift = float(court["diff"])
        lo, mid, hi = lo + shift, mid + shift, hi + shift
    floor = min_price_krw / appraisal_krw * 100 if min_price_krw and appraisal_krw else None
    below = bool(floor and hi < floor)
    if floor:
        lo, mid, hi = max(lo, floor), max(mid, floor), max(hi, floor)
    return {"lo": lo, "mid": mid, "hi": hi, "shift": shift, "below": below}


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


RECENT_DAYS = 120  # 관할 법원 칸·같은 구 참고: 최근 3~4개월
COURT_MIN_N = 30
COURT_SHIFT_PP = 3.0


def _near(s: Sale, min_rate: float | None) -> bool:
    return min_rate is None or s.min_rate is None or abs(s.min_rate - min_rate) <= 3


def court_cell(
    sales: list[Sale],
    *,
    as_of: date,
    court_code: str | None,
    usage_name: str | None,
    min_rate: float | None,
    base_p50: float | None,
) -> RuleResult:
    """관할 법원 칸: 같은 법원·같은 용도·최저가율 ±3%p·최근 120일 매각.

    30건 이상이고 지역 기준(base_p50)과 3%p 이상 차이 나면 use_as_base=True —
    법원마다 같은 조건이어도 낙찰가율이 10%p 넘게 벌어지는 일이 있어서입니다. [추정]
    """
    if not court_code:
        return RuleResult(None, Status.UNKNOWN, "sale_rate.court.none", [])
    since = as_of - timedelta(days=RECENT_DAYS)
    pool = [
        s.sale_rate for s in sales
        if s.court_code == court_code and s.usage_name == usage_name and since <= s.sale_date <= as_of
        and not s.is_special_case and _in_trim(s) and _near(s, min_rate)
    ]  # fmt: skip
    if not pool:
        return RuleResult(None, Status.UNKNOWN, "sale_rate.court.none", [{"court": court_code}])
    p50 = _quantile(pool, 0.5)
    diff = round(p50 - base_p50, 1) if base_p50 is not None else None
    use = len(pool) >= COURT_MIN_N and diff is not None and abs(diff) >= COURT_SHIFT_PP
    value = {
        "p50": p50,
        "p75": _quantile(pool, 0.75),
        "n": len(pool),
        "diff": diff,
        "use_as_base": use,
    }
    return RuleResult(value, Status.ESTIMATED, "sale_rate.court", [{"court": court_code}])


def local_peers(
    sales: list[Sale],
    *,
    as_of: date,
    sigungu: str | None,
    usage_name: str | None,
    min_rate: float | None,
    review_p50: float | None,
) -> RuleResult:
    """같은 구·같은 용도·같은 회차의 최근 매각 「상단 참고」. 3건 이상일 때만.

    계수로 쓰지 않고, 우리 검토값이 그 범위 최저보다 10%p 이상 낮으면 warn=True.
    """
    since = as_of - timedelta(days=RECENT_DAYS)
    pool = [
        s.sale_rate for s in sales
        if sigungu and s.sigungu == sigungu and s.usage_name == usage_name
        and since <= s.sale_date <= as_of and not s.is_special_case and _in_trim(s) and _near(s, min_rate)
    ]  # fmt: skip
    if len(pool) < 3:
        return RuleResult(None, Status.UNKNOWN, "sale_rate.local.few", [{"n": len(pool)}])
    lo, hi = min(pool), max(pool)
    warn = review_p50 is not None and lo - review_p50 >= 10
    value = {"n": len(pool), "lo": round(lo, 1), "hi": round(hi, 1), "warn": warn}
    return RuleResult(value, Status.ESTIMATED, "sale_rate.local", [])


def effective_failed(
    failed_count: int | None, appraisal_krw: int | None, min_price_krw: int | None
) -> int:
    """낙찰가율 표본을 고를 때 쓰는 유찰 횟수.

    유찰이 있었어도 최저가가 감정가 그대로면(임차인 대항력 포기 등 매각조건이 바뀌어
    법원이 감정가부터 다시 시작) 처음 나온 물건과 같은 자리라 0으로 봅니다.
    """
    if appraisal_krw and min_price_krw and min_price_krw >= appraisal_krw:
        return 0
    return failed_count or 0


def restarted(
    failed_count: int | None, appraisal_krw: int | None, min_price_krw: int | None
) -> bool:
    """유찰이 있었는데 최저가가 감정가로 돌아온 물건."""
    return bool(failed_count) and effective_failed(failed_count, appraisal_krw, min_price_krw) == 0


def new_item(
    failed_count: int | None, appraisal_krw: int | None, market_krw: int | None
) -> RuleResult:
    """신건(유찰 0회): 최저가 = 감정가라 보통 감정가 이상에 팔립니다. 범위 계산을 내놓지 않습니다.

    예외: 감정가 ≤ 실거래 시세 × 0.8 이면 계산을 엽니다(감정가가 많이 낮은 경우). [추정]
    """
    if (failed_count or 0) > 0:
        return RuleResult(False, Status.CONFIRMED, "sale_rate.new.no", [])
    if appraisal_krw and market_krw and appraisal_krw <= market_krw * 0.8:
        return RuleResult(
            False, Status.ESTIMATED, "sale_rate.new.open", [{"ratio": appraisal_krw / market_krw}]
        )
    return RuleResult(True, Status.ESTIMATED, "sale_rate.new", [])
