"""예상 배당 (민사집행법 제145조 등). 「떠안는 돈이 있는가」를 보기 위한 단순 계산입니다.

순서: 경매비용 → 최우선변제(소액임차인) → 당해세 → 날짜 순(담보·확정일자 임차인·법정기일 조세)
     → 가압류 등 일반채권 안분. 가압류의 안분흡수는 단순화했으므로 결과는 항상 「추정」.
"""

from dataclasses import dataclass

from aucs_rules.result import RuleResult, Status


@dataclass(frozen=True)
class Claim:
    name: str
    kind: str  # cost / top_priority / local_tax / dated / general
    amount_krw: int | None
    rank_date: object = None  # date — dated 만 사용 (같은 날은 들어온 순서)


def distribute(sale_price_krw: int, claims: list[Claim]) -> RuleResult:
    """낙찰가를 순서대로 나눕니다. 금액 모르는 채권이 있으면 「확인 필요」."""
    if sale_price_krw < 0:
        return RuleResult(None, Status.NEEDS_CHECK, "dist.negative", [])
    left = sale_price_krw
    paid: dict[str, int] = {}
    unknown = [c.name for c in claims if c.amount_krw is None]
    known = [c for c in claims if c.amount_krw is not None]

    def pay_in_order(group: list[Claim]) -> None:
        nonlocal left
        for c in group:
            pay = min(left, c.amount_krw or 0)
            paid[c.name] = paid.get(c.name, 0) + pay
            left -= pay

    pay_in_order([c for c in known if c.kind == "cost"])
    left = _pay_group([c for c in known if c.kind == "top_priority"], left, paid)
    pay_in_order([c for c in known if c.kind == "local_tax"])
    pay_in_order(
        sorted([c for c in known if c.kind == "dated"], key=lambda c: str(c.rank_date or ""))
    )
    left = _pay_group([c for c in known if c.kind == "general"], left, paid)
    status = Status.NEEDS_CHECK if unknown else Status.ESTIMATED
    ev = [{"unknown_amount": unknown}] if unknown else []
    return RuleResult({"paid": paid, "surplus_krw": left}, status, "dist.simple", ev)


def _pay_group(group: list[Claim], left: int, paid: dict[str, int]) -> int:
    """같은 순위끼리 금액 비율로 나눔(안분)."""
    total = sum(c.amount_krw or 0 for c in group)
    if total == 0:
        return left
    pool = min(left, total)
    for c in group:
        paid[c.name] = paid.get(c.name, 0) + pool * (c.amount_krw or 0) // total
    return left - pool
