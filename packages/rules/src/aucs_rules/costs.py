"""실질 취득가·입찰 상한·전액 현금 (04탭 6절 4단계). 낙찰가가 아니라 실제로 드는 돈으로 판단합니다.

실질 취득가 = 낙찰가 + 떠안는 돈(보증금·전세권·세금 선배분으로 모자란 몫) + 숨은 비용 + 취득세 등.
입찰 상한 = 시세 − (떠안는 돈 + 숨은 비용 + 취득세 + 목표 이익).
"""

from typing import Any

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


PYEONG_M2 = 3.3058


def _round_man(x: float) -> int:
    """만 원 단위로."""
    return int(round(x / 10_000)) * 10_000


def move_out_cost(
    area_m2: float | None, *, floor: int | None, elevators: int | None, table: dict[str, Any]
) -> dict[str, Any]:
    """명도비 대략 범위(10/27): 협의 이사비 ~ 강제집행 비용. 면적을 모르면 최소액 범위. [추정]

    승강기가 없고(대장에 0 또는 없음) 3층 이상이면 위쪽에 30%를 더함.
    """
    t = table["move_out"]
    lo_min, hi_min = t["min_krw"]
    pp_lo, pp_hi = t["per_pyeong_krw"]
    py = (area_m2 or 0) / PYEONG_M2
    lo, hi = max(py * pp_lo, lo_min), max(py * pp_hi, hi_min)
    stairs = bool(floor and floor >= t["no_elevator_from_floor"] and not elevators)
    if stairs:
        hi *= 1 + t["no_elevator_add_pct"] / 100
    lo, hi = _round_man(lo), _round_man(hi)
    return {"low_krw": lo, "high_krw": hi, "mid_krw": _round_man((lo + hi) / 2), "stairs": stairs,
            "basis": "area" if area_m2 else "min"}  # fmt: skip


def repair_cost(
    area_m2: float | None, *, age_years: int | None, table: dict[str, Any]
) -> dict[str, Any]:
    """수리비 대략 범위: 사용승인 연식별 전용 평당. 연식·면적을 모르면 넓은 범위 또는 None. [추정]"""
    if not area_m2:
        return {"low_krw": None, "high_krw": None, "mid_krw": 0, "basis": "none"}
    t = table["repair"]
    band = t["unknown"]
    if age_years is not None:
        band = next((b for lim, b in t["bands"] if age_years < lim), t["bands"][-1][1])
    py = area_m2 / PYEONG_M2
    lo, hi = _round_man(py * band[0]), _round_man(py * band[1])
    return {"low_krw": lo, "high_krw": hi, "mid_krw": _round_man((lo + hi) / 2),
            "basis": "age" if age_years is not None else "unknown_age"}  # fmt: skip


def rent_returns(
    total_krw: int,
    *,
    cls: str,
    loan_krw: int,
    rate_pct: float,
    jeonse_krw: int | None,
    wolse_deposit_krw: int | None,
    wolse_rent_krw: int | None,
) -> dict[str, Any] | None:
    """세놓으면(옥스 기능 9, 10/27): 같은 단지 전월세 가운데 값으로 묶이는 돈·연 수익·현금 수익률. [추정]

    수도권·규제지역은 주담대를 받으면 6개월 안에 들어가 살아야 해서 세놓기는 대출 없이 계산.
    total_krw = 낙찰가 + 취득세 + 등기 + 떠안는 돈 + 명도·수리(실제로 드는 돈 전부).
    """
    if not jeonse_krw and not wolse_rent_krw:
        return None
    no_loan = cls in ("regulated", "metro")
    loan = 0 if no_loan else loan_krw
    interest = int(loan * rate_pct / 100)
    out: dict[str, Any] = {
        "loan_krw": loan,
        "no_loan_reason": "move_in_rule" if no_loan and loan_krw else None,
    }
    if jeonse_krw:
        out["jeonse"] = {"deposit_krw": jeonse_krw, "cash_krw": total_krw - jeonse_krw - loan,
                         "interest_krw": interest}  # fmt: skip
    if wolse_rent_krw:
        dep = wolse_deposit_krw or 0
        cash = total_krw - dep - loan
        net = wolse_rent_krw * 12 - interest
        out["wolse"] = {
            "deposit_krw": dep, "rent_krw": wolse_rent_krw, "cash_krw": cash, "net_year_krw": net,
            "yield_pct": round(net * 100 / cash, 1) if cash > 0 else None,
        }  # fmt: skip
    return out
