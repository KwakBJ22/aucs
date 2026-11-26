"""입찰가 계산 (CALC-01): 대출·취득세·필요한 현금·세 경우.

바뀌는 숫자(규제지역·대출 비율·한도·세율)는 기준표(ref.rule_tables)에서 받습니다 — 인자 `tables`.
대출은 규정상 최대치일 뿐 소득(DSR)·은행에 따라 줄어듭니다. 화면에서 손님이 직접 바꿀 수 있게 합니다.
"""

import re
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
    # 11/25: 새로 생긴 구(화성시 동탄구)는 법원 주소에 구 이름이 없음(「화성시 오산동 …」) → 법정동으로
    for city, dongs in (regulated.get("gyeonggi_dongs") or {}).items():
        if re.search(rf"{city}\s+(?:\S+구\s+)?(?:{'|'.join(dongs)})(?:\s|$)", addr):
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
    kind: str = "house",
) -> RuleResult:
    """규정상 최대 대출. 기준 가격 = min(낙찰가, 감정가, 시세) × 비율, 지역별 한도 적용.

    selling: 1주택자가 기존 집을 처분하는 조건(처분 조건부) — 표에 owner_sell 이 있으면 그 비율.
    """
    basis = min(x for x in (bid_krw, appraisal_krw, market_krw) if x)
    if kind != "house":  # 11/17 — 기준표는 주택담보대출 비율. 상가 · 오피스텔 · 땅은 은행마다 달라 셈하지 않음
        note = (
            "대출 없이 계산했어요 — 주택이면 「바꾸기」로 받을 금액을 넣어 주세요"
            if kind == "unknown"
            else "상가·오피스텔·땅 대출은 은행마다 달라요 — 「바꾸기」로 받을 금액을 넣어 주세요"
        )
        value = {"loan_krw": 0, "pct": None, "cap_krw": None, "basis_krw": basis,
                 "who": "unknown" if kind == "unknown" else "non_house", "note": note}  # fmt: skip
        return RuleResult(value, Status.UNKNOWN, f"calc.loan.{cls}", [{"kind": kind}])
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


# 주택 아닌 것의 유상취득(지방세법 §11①7: 농지 3% · 그 밖 4%) — 본세 · 지방교육세 · 농특세(11/16).
# 기준표 acquisition_tax.non_house 가 있으면 그것을 씀
NON_HOUSE = {"other": {"rate": 4.0, "edu": 0.4, "farm": 0.2}, "farm": {"rate": 3.0, "edu": 0.2, "farm": 0.2}}
_HOUSE = re.compile(r"(아파트|다세대|연립|빌라|단독|다가구|주택|주거용)")  # 공매 「기타주거용건물」


# 주택이 아니라고 확인되는 말(법원 · 공매 용도, 건축물대장 주용도)
_NON_HOUSE = re.compile(
    r"(근린|상가|오피스텔|공장|업무|사무|판매|숙박|창고|교육|노유자|의료|운동|종교|문화|위락|자동차|주차|"
    r"임야|대지|잡종지|도로|토지|목장|염전|하천|구거|유지|제방|묘지|체육|학교|철도|수도|공원|기숙사|빌딩|시설)"
)


def tax_kind(usage: str | None) -> str:
    """물건 용도 글 → 취득세 · 대출 종류: house(주택 1~3%·중과) · farm(전답 3%) · other(상가 · 오피스텔 · 땅 4%)
    · unknown(주택인지 아닌지 확인할 말이 없음 — 법원 용도 「기타」에 대장도 없는 물건 등).
    오피스텔은 취득세에서 주택이 아님. 11/17 정직 원칙: 확인 안 되면 짐작해 셈하지 않고 unknown."""
    u = (usage or "").strip()
    if _HOUSE.search(u):
        return "house"
    if u and u.split()[0] in ("전답", "전", "답", "과수원"):  # 경매 「전답」 · 공매 「전」 「답」
        return "farm"
    if _NON_HOUSE.search(u):
        return "other"
    return "unknown"


def usage_for_kind(
    court: str | None, desc: str | None, unit_use: str | None, main_use: str | None
) -> str:
    """취득세 · 대출 종류를 가를 글(11/17): 그 호의 대장 전유 용도 → 법원 용도 + 물건 설명 → 대장 주용도(건물 전체) 순.
    예전엔 셋을 이어 붙여 주택 말이 하나라도 있으면 주택으로 셈 — 주상복합 건물의 상가 · 오피스텔 호가 건물 주용도의
    「공동주택」 때문에 주택 비율로 대출이 셈해졌음(더파인빌딩 805호). 근생빌라 호는 전유 용도대로 주택 아님.

    0.19.5(11/17 대표님): 그 호 대장과 법원 용도가 주택 / 주택 아님으로 갈리면 주택 아닌 쪽으로 — 취득세 주택 세율은
    「대장(등기부)에 주택으로 기재 + 실제 주거용」 둘 다여야 함(지방세법 제11조 제1항 제8호, 조심 2018지986)."""
    court_text = " ".join(x for x in (court, desc) if x)
    kinds = {tax_kind(unit_use), tax_kind(court_text)} if unit_use else set()
    if "house" in kinds and kinds & {"other", "farm"}:
        return unit_use if tax_kind(unit_use) != "house" else court_text  # type: ignore[return-value]
    for u in (unit_use, court_text, main_use):
        if u and tax_kind(u) != "unknown":
            return u
    return ""


def acquisition_tax(
    price_krw: int,
    *,
    homes_after: int,
    cls: str,
    area_m2: float | None,
    table: dict[str, Any],
    temporary_two: bool = False,
    relief: dict[str, Any] | None = None,
    kind: str = "house",
) -> RuleResult:
    """주택 취득세 + 지방교육세 + 농특세(85㎡ 초과). homes_after = 이번 집을 포함한 주택 수.
    kind 가 farm · other 면 집 수와 상관없이 정해진 세율(11/16 — 상가 · 땅에 주택 세율이 붙던 것).

    temporary_two: 일시적 2주택(새 집을 사고 3년 안에 기존 집 처분) → 중과 대신 기본 세율 (지방세법 시행령 §28의5).
    relief: 생애최초 감면 표(지방세특례제한법 §36의3) — 넣으면 취득세 본세에서 한도까지 뺍니다.
    """
    if kind == "unknown":  # 용도 확인 안 됨 — 세율을 짐작하지 않음(필요한 현금에서 빠짐, 화면에 그렇게 적음)
        return RuleResult(
            {"tax_krw": 0, "relief_krw": 0, "rate": None, "total_pct": None, "heavy": False,
             "temporary_two": False, "kind": "unknown"},
            Status.UNKNOWN, "calc.acq_tax", [{"kind": kind}],
        )  # fmt: skip
    if kind in ("farm", "other"):
        nh = {**NON_HOUSE, **(table.get("non_house") or {})}[kind]
        total = float(nh["rate"]) + float(nh["edu"]) + float(nh["farm"])
        return RuleResult(
            {"tax_krw": int(price_krw * total / 100), "relief_krw": 0, "rate": float(nh["rate"]),
             "total_pct": round(total, 3), "heavy": False, "temporary_two": False, "kind": kind},
            Status.ESTIMATED, "calc.acq_tax", [{"kind": kind}],
        )  # fmt: skip
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
        # 11/25: 기본 세율 구간도 기준표(basic)에서 — 세법이 바뀌면 새 줄만 넣으면 됨(전엔 코드에 1 · 공식 · 3% 고정)
        eok = price_krw / 100_000_000
        rate = 3.0
        for upper, r in table.get("basic") or [[600_000_000, 1.0], [900_000_000, "formula"], [None, 3.0]]:
            if upper is None or price_krw <= int(upper):
                # 지방세법 §11①8: 6억 초과 9억 이하 = 취득가(억) × 2/3 − 3, 소수점 다섯째 자리에서 반올림
                rate = round(eok * 2 / 3 - 3, 4) if r == "formula" else float(r)
                break
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
    usage: str | None = None,
    tables: dict[str, Any],
) -> RuleResult:
    """입찰가 하나에 대한 필요한 현금. 떠안는 돈이 있으면 대출이 어렵다고 보고 0으로.

    소득을 넣으면 대출 = min(규정 최대, 소득 기준 최대). 1주택 + selling 이면 일시적 2주택·처분 조건부.
    """
    kind = tax_kind(usage)
    loan = loan_limit(
        bid_krw, appraisal_krw=appraisal_krw, market_krw=market_krw, cls=cls,
        homes=homes, first_time=first_time, table=tables["loan_ltv"], selling=selling, kind=kind,
    ).value  # fmt: skip
    dsr = None
    if income_krw and "dsr" in tables and kind == "house":
        dsr = dsr_limit(
            income_krw, other_monthly_krw=other_monthly_krw, cls=cls, table=tables["dsr"]
        ).value
        if dsr["loan_krw"] < loan["loan_krw"]:
            loan = {**loan, "loan_krw": dsr["loan_krw"], "by_dsr": True}
    loan_krw = loan["loan_krw"] if loan_override_krw is None else min(loan_override_krw, bid_krw)
    if assumed_krw > 0 and loan_override_krw is None:
        loan_krw = 0
    relief = tables.get("first_home_relief") if first_time and homes == 0 and kind == "house" else None
    tax = acquisition_tax(
        bid_krw + assumed_krw, homes_after=homes + 1, cls=cls, area_m2=area_m2,
        table=tables["acquisition_tax"], temporary_two=selling, relief=relief, kind=kind,
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
        bid = max(round(appraisal_krw * pct / 100) // 10_000 * 10_000, min_price_krw)  # 11/25: 87.1% 가 1만 원 모자라게 셈됨(부동소수)
        out.append({"key": key, "bid_krw": bid, "rate": pct, "chance": chance})
    return out


# 찾기·추천의 「가진 현금」 기준에 쓰는 표(11/9) — 분석이 물건마다 적어 둠
CASH_TABLE_KEYS = ("regulated_areas", "loan_ltv", "acquisition_tax")


def cash_at_min(
    *,
    min_price_krw: int,
    appraisal_krw: int | None,
    market_krw: int | None,
    area_m2: float | None,
    sido: str | None,
    address: str | None,
    tables: dict[str, Any],
    usage: str | None = None,
) -> dict[str, int]:
    """최저가에 낙찰받을 때 필요한 현금(낙찰가 − 규정상 최대 대출 + 취득세 · 등기), 가진 집 수별 {"0","1","2"}.
    입찰가 계산 화면(cash_needed)과 같은 셈 — 명도·수리비와 떠안는 돈은 빼고(물건마다 달라 계산 화면에서)."""
    cls = area_class(sido, address, tables["regulated_areas"])
    out: dict[str, int] = {}
    for homes in (0, 1, 2):
        v = cash_needed(
            min_price_krw, min_price_krw=min_price_krw, appraisal_krw=appraisal_krw,
            market_krw=market_krw, area_m2=area_m2, cls=cls, homes=homes, first_time=False,
            usage=usage, tables=tables,
        ).value  # fmt: skip
        out[str(homes)] = int(v["cash_krw"])
    # 11/18: 용도 확인 안 됨 — 취득세가 빠진 금액이라는 표시(찾기 「가진 현금」 비교 · 카드 한 줄)
    if tax_kind(usage) == "unknown":
        out["notax"] = 1
    return out
