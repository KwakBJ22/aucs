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
    selling: bool = False,
) -> RuleResult:
    """규정상 최대 대출. 기준 가격 = min(낙찰가, 감정가, 시세) × 비율, 지역별 한도 적용.

    selling: 1주택자가 기존 집을 처분하는 조건(처분 조건부) — 표에 owner_sell 이 있으면 그 비율.
    """
    basis = min(x for x in (bid_krw, appraisal_krw, market_krw) if x)
    if homes >= 1:
        who = "owner_sell" if selling and homes == 1 and "owner_sell" in table[cls] else "owner"
    else:
        who = "first_time" if first_time else "none"
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
    price_krw: int,
    *,
    homes_after: int,
    cls: str,
    area_m2: float | None,
    table: dict[str, Any],
    temporary_two: bool = False,
    relief: dict[str, Any] | None = None,
) -> RuleResult:
    """주택 취득세 + 지방교육세 + 농특세(85㎡ 초과). homes_after = 이번 집을 포함한 주택 수.

    temporary_two: 일시적 2주택(새 집을 사고 3년 안에 기존 집 처분) → 중과 대신 기본 세율 (지방세법 시행령 §28의5).
    relief: 생애최초 감면 표(지방세특례제한법 §36의3) — 넣으면 취득세 본세에서 한도까지 뺍니다.
    """
    heavy_tbl = table["heavy"]["regulated" if cls == "regulated" else "other"]
    heavy = None
    skip_heavy = temporary_two and homes_after == 2
    for n in [] if skip_heavy else sorted((int(k) for k in heavy_tbl), reverse=True):
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
    gross = int(price_krw * total_pct / 100)
    cut = 0
    if relief and price_krw <= int(relief["price_max_krw"]):
        cut = min(int(relief["max_krw"]), int(price_krw * rate / 100))
    value = {
        "tax_krw": gross - cut,
        "relief_krw": cut,
        "rate": rate,
        "total_pct": round(total_pct, 3),
        "heavy": heavy is not None,
        "temporary_two": skip_heavy,
    }
    return RuleResult(value, Status.ESTIMATED, "calc.acq_tax", [{"homes_after": homes_after}])


def dsr_limit(
    income_krw: int, *, other_monthly_krw: int = 0, cls: str, table: dict[str, Any]
) -> RuleResult:
    """소득으로 받을 수 있는 최대 주담대(차주 DSR). 원리금균등, 금리 = 기준 + 스트레스 가산(한도 계산용).

    연 원리금 합계 ≤ 연 소득 × limit_pct. 다른 대출 월 상환액을 먼저 뺍니다.
    """
    r = (float(table["base_rate_pct"]) + float(table["stress_pp"][cls])) / 100 / 12
    n = int(table["years"]) * 12
    monthly_cap = income_krw * float(table["limit_pct"]) / 100 / 12 - other_monthly_krw
    if monthly_cap <= 0:
        return RuleResult(
            {"loan_krw": 0, "rate_pct": round(r * 1200, 2)}, Status.ESTIMATED, "calc.dsr.none", []
        )
    loan = int(monthly_cap * (1 - (1 + r) ** -n) / r)
    value = {"loan_krw": loan, "rate_pct": round(r * 1200, 2), "monthly_cap_krw": int(monthly_cap)}
    return RuleResult(value, Status.ESTIMATED, "calc.dsr", [])


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
    move_out_krw: int = 0,
    repair_krw: int = 0,
    loan_override_krw: int | None = None,
    deposit_rate_pct: float = 10.0,
    selling: bool = False,
    income_krw: int | None = None,
    other_monthly_krw: int = 0,
    tables: dict[str, Any],
) -> RuleResult:
    """입찰가 하나에 대한 필요한 현금. 떠안는 돈이 있으면 대출이 어렵다고 보고 0으로.

    소득을 넣으면 대출 = min(규정 최대, 소득 기준 최대). 1주택 + selling 이면 일시적 2주택·처분 조건부.
    """
    loan = loan_limit(
        bid_krw, appraisal_krw=appraisal_krw, market_krw=market_krw, cls=cls,
        homes=homes, first_time=first_time, table=tables["loan_ltv"], selling=selling,
    ).value  # fmt: skip
    dsr = None
    if income_krw and "dsr" in tables:
        dsr = dsr_limit(
            income_krw, other_monthly_krw=other_monthly_krw, cls=cls, table=tables["dsr"]
        ).value
        if dsr["loan_krw"] < loan["loan_krw"]:
            loan = {**loan, "loan_krw": dsr["loan_krw"], "by_dsr": True}
    loan_krw = loan["loan_krw"] if loan_override_krw is None else min(loan_override_krw, bid_krw)
    if assumed_krw > 0 and loan_override_krw is None:
        loan_krw = 0
    relief = tables.get("first_home_relief") if first_time and homes == 0 else None
    tax = acquisition_tax(
        bid_krw + assumed_krw, homes_after=homes + 1, cls=cls, area_m2=area_m2,
        table=tables["acquisition_tax"], temporary_two=selling, relief=relief,
    ).value  # fmt: skip
    reg = registration_cost(bid_krw)
    deposit = -(-min_price_krw * int(deposit_rate_pct * 100) // 10_000)
    extra = move_out_krw + repair_krw  # 명도비·수리비(대략, 가운데 값) — 10/27
    cash = bid_krw - loan_krw + tax["tax_krw"] + reg + assumed_krw + extra
    value = {
        "bid_krw": bid_krw,
        "deposit_krw": deposit,
        "loan_krw": loan_krw,
        "loan": loan,
        "dsr": dsr,
        "tax": tax,
        "registration_krw": reg,
        "assumed_krw": assumed_krw,
        "move_out_krw": move_out_krw,
        "repair_krw": repair_krw,
        "cash_krw": cash,
        "total_krw": bid_krw + tax["tax_krw"] + reg + assumed_krw + extra,
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
