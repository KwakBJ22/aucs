"""입찰가 계산 (CALC-01): 대출·취득세·필요한 현금·세 경우.

바뀌는 숫자(규제지역·대출 비율·한도·세율)는 기준표(ref.rule_tables)에서 받습니다 — 인자 `tables`.
대출은 규정상 최대치일 뿐 소득(DSR)·은행에 따라 줄어듭니다. 화면에서 손님이 직접 바꿀 수 있게 합니다.
"""

from typing import Any

from aucs_rules.result import RuleResult, Status

METRO = ("서울", "경기", "인천")


def area_class(sido: str | None, address: str | None, regulated: dict[str, Any]) -> str:
    """regulated(규제지역) / metro(수도권 비규제) / other."""
    sd = sido or ""
    if sd.startswith("서울") and regulated.get("seoul_all"):
        return "regulated"
    addr = " ".join((address or "").split())
    if any(name in addr for name in regulated.get("gyeonggi", [])):
        return "regulated"
    return "metro" if sd.startswith(METRO) else "other"


def loan_limit(
    bid_krw: int,
    *,
    appraisal_krw: int | None,
    market_krw: int | None,
    cls: str,
    homes: int,
    first_time: bool,
    table: dict[str, Any],
) -> RuleResult:
    """규정상 최대 대출. 기준 가격 = min(낙찰가, 감정가, 시세) × 비율, 지역별 한도 적용."""
    basis = min(x for x in (bid_krw, appraisal_krw, market_krw) if x)
    who = "owner" if homes >= 1 else "first_time" if first_time else "none"
    pct = float(table[cls][who])
    amount = int(basis * pct / 100)
    cap = None
    if cls == "regulated":
        price = market_krw or appraisal_krw or bid_krw
        for upper, c in table["caps_regulated"]:
            if upper is None or price <= upper:
                cap = int(c)
                break
    elif cls == "metro":
        cap = int(table["cap_metro_krw"])
    if cap is not None:
        amount = min(amount, cap)
    note = "기존 집을 처분하는 조건이면 가능할 수 있어요" if who == "owner" and pct == 0 else None
    value = {
        "loan_krw": amount,
        "pct": pct,
        "cap_krw": cap,
        "basis_krw": basis,
        "who": who,
        "note": note,
    }
    return RuleResult(value, Status.ESTIMATED, f"calc.loan.{cls}", [{"cls": cls}])


def acquisition_tax(
    price_krw: int, *, homes_after: int, cls: str, area_m2: float | None, table: dict[str, Any]
) -> RuleResult:
    """주택 취득세 + 지방교육세 + 농특세(85㎡ 초과). homes_after = 이번 집을 포함한 주택 수."""
    heavy_tbl = table["heavy"]["regulated" if cls == "regulated" else "other"]
    heavy = None
    for n in sorted((int(k) for k in heavy_tbl), reverse=True):
        if homes_after >= n:
            heavy = float(heavy_tbl[str(n)])
            break
    if heavy is not None:
        rate = heavy
        edu = float(table["edu_heavy"])
        farm_key = str(int(heavy))
    else:
        eok = price_krw / 100_000_000
        if price_krw <= 600_000_000:
            rate = 1.0
        elif price_krw <= 900_000_000:
            rate = round(eok * 2 / 3 - 3, 4)  # 지방세법 §11①8: 소수점 다섯째 자리에서 반올림
        else:
            rate = 3.0
        edu = rate * float(table["edu_rate_of_basic"]) / 100
        farm_key = "basic"
    farm = float(table["farm_over85"][farm_key]) if area_m2 and area_m2 > 85 else 0.0
    total_pct = rate + edu + farm
    value = {
        "tax_krw": int(price_krw * total_pct / 100),
        "rate": rate,
        "total_pct": round(total_pct, 3),
        "heavy": heavy is not None,
    }
    return RuleResult(value, Status.ESTIMATED, "calc.acq_tax", [{"homes_after": homes_after}])


def registration_cost(price_krw: int) -> int:
    """등기·법무사 비용 대략치: 낙찰가의 0.2%, 최소 50만 원. [추정]"""
    return max(int(price_krw * 0.002), 500_000)


def cash_needed(
    bid_krw: int,
    *,
    min_price_krw: int,
    appraisal_krw: int | None,
    market_krw: int | None,
    area_m2: float | None,
    cls: str,
    homes: int,
    first_time: bool,
    assumed_krw: int = 0,
    loan_override_krw: int | None = None,
    deposit_rate_pct: float = 10.0,
    tables: dict[str, Any],
) -> RuleResult:
    """입찰가 하나에 대한 필요한 현금. 떠안는 돈이 있으면 대출이 어렵다고 보고 0으로."""
    loan = loan_limit(
        bid_krw, appraisal_krw=appraisal_krw, market_krw=market_krw, cls=cls,
        homes=homes, first_time=first_time, table=tables["loan_ltv"],
    ).value  # fmt: skip
    loan_krw = loan["loan_krw"] if loan_override_krw is None else min(loan_override_krw, bid_krw)
    if assumed_krw > 0 and loan_override_krw is None:
        loan_krw = 0
    tax = acquisition_tax(
        bid_krw + assumed_krw, homes_after=homes + 1, cls=cls, area_m2=area_m2,
        table=tables["acquisition_tax"],
    ).value  # fmt: skip
    reg = registration_cost(bid_krw)
    deposit = -(-min_price_krw * int(deposit_rate_pct * 100) // 10_000)
    cash = bid_krw - loan_krw + tax["tax_krw"] + reg + assumed_krw
    value = {
        "bid_krw": bid_krw,
        "deposit_krw": deposit,
        "loan_krw": loan_krw,
        "loan": loan,
        "tax": tax,
        "registration_krw": reg,
        "assumed_krw": assumed_krw,
        "cash_krw": cash,
        "total_krw": bid_krw + tax["tax_krw"] + reg + assumed_krw,
    }
    return RuleResult(value, Status.ESTIMATED, "calc.cash", [])


def bid_cases(
    appraisal_krw: int, min_price_krw: int, p25: float, p50: float, p75: float
) -> list[dict[str, Any]]:
    """세 경우: 예상 낙찰 범위의 아래·가운데·위 (만 원 단위로 끝자리 정리, 최저가 미만이면 최저가)."""
    out = []
    for key, pct, chance in (("low", p25, "낮음"), ("mid", p50, "보통"), ("high", p75, "높음")):
        bid = max(int(appraisal_krw * pct / 100) // 10_000 * 10_000, min_price_krw)
        out.append({"key": key, "bid_krw": bid, "rate": pct, "chance": chance})
    return out
