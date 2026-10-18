"""실질 취득가·입찰 상한·전액 현금 (04탭 6절 4단계). 낙찰가가 아니라 실제로 드는 돈으로 판단합니다.

실질 취득가 = 낙찰가 + 떠안는 돈(보증금·전세권·세금 선배분으로 모자란 몫) + 숨은 비용 + 취득세 등.
입찰 상한 = 시세 − (떠안는 돈 + 숨은 비용 + 취득세 + 목표 이익).
"""

from aucs_rules.result import RuleResult, Status


def real_cost(
    bid_krw: int, *, assumed_krw: int = 0, hidden_krw: int = 0, tax_krw: int = 0
) -> RuleResult:
    """실질 취득가. 떠안는 돈이 있으면 대출이 어렵다고 보고 전액 현금을 같이 냅니다."""
    total = bid_krw + assumed_krw + hidden_krw + tax_krw
    value = {
        "total_krw": total,
        "parts": {"bid": bid_krw, "assumed": assumed_krw, "hidden": hidden_krw, "tax": tax_krw},
        "full_cash_krw": total if assumed_krw > 0 else None,
    }
    status = Status.ESTIMATED if (assumed_krw or hidden_krw) else Status.CONFIRMED
    return RuleResult(value, status, "costs.real", [])


def bid_cap(
    market_krw: int | None,
    *,
    assumed_krw: int = 0,
    hidden_krw: int = 0,
    tax_krw: int = 0,
    margin_krw: int = 0,
    min_price_krw: int | None = None,
) -> RuleResult:
    """입찰 상한(이 금액을 넘으면 손해). 최저가보다 낮게 나오면 「어떤 값에도 남는 게 없어요」."""
    if market_krw is None:
        return RuleResult(None, Status.UNKNOWN, "costs.cap.no_market", [])
    cap = market_krw - assumed_krw - hidden_krw - tax_krw - margin_krw
    no_gain = cap <= 0 or (min_price_krw is not None and cap < min_price_krw)
    value = {"cap_krw": max(cap, 0), "no_gain": no_gain}
    return RuleResult(value, Status.ESTIMATED, "costs.cap", [{"market_krw": market_krw}])


def commercial_over_limit(
    deposit_krw: int | None,
    monthly_rent_krw: int | None,
    *,
    sido: str | None,
    sigungu: str | None,
    region_class: str | None,
    table: dict,  # type: ignore[type-arg]
) -> RuleResult:
    """상가 환산보증금(보증금 + 월세×100)이 지역 한도를 넘는지 (상가건물 임대차보호법 시행령 §2).

    상가 지역 구분은 주택과 다릅니다: 부산은 과밀 칸, 세종·파주·화성·안산·용인·김포·광주(경기)는 metro 칸.
    """
    if deposit_krw is None:
        return RuleResult(None, Status.UNKNOWN, "lease.commercial.no_deposit", [])
    mult = int(table.get("rent_multiplier", 100))
    conv = deposit_krw + (monthly_rent_krw or 0) * mult
    names = {
        (sido or "").replace("특별시", "").replace("광역시", ""),
        (sigungu or "").rstrip("시군"),
    }
    cls = next(
        (k for k in ("metro", "overcrowded") if names & set(table.get(k, {}).get("also", []))),
        region_class,
    )
    if cls not in table:
        return RuleResult(
            None, Status.UNKNOWN, "lease.commercial.no_region", [{"converted_krw": conv}]
        )
    limit = int(table[cls]["limit_krw"])
    value = {"over": conv > limit, "converted_krw": conv, "limit_krw": limit, "region": cls}
    return RuleResult(value, Status.ESTIMATED, "lease.commercial", [])
