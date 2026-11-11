"""주택 보유세(TAX-02): 공시가격으로 해마다 내는 재산세·종합부동산세 어림 (11/11 대표님).

세율·비율은 기준표(ref.rule_tables 'property_tax_home'·'comprehensive_tax_home')에서 읽음.
세부담상한·고령자·장기보유 세액공제는 넣지 않아 실제보다 많게 나올 수 있음 → 결과는 늘 「추정」.
"""

from typing import Any

from aucs_rules.result import RuleResult, Status


def _progressive(base: float, brackets: list[list[Any]]) -> float:
    """누진 세율표 [[구간 끝(원)|None, 세율(%)]…] 로 세액."""
    tax, prev = 0.0, 0.0
    for upto, rate in brackets:
        top = base if upto is None else min(base, float(upto))
        if top > prev:
            tax += (top - prev) * float(rate) / 100
        if upto is None or base <= float(upto):
            break
        prev = float(upto)
    return tax


def _step(value: float, steps: list[list[Any]]) -> float:
    """구간표 [[끝|None, 값]…] 에서 value 가 드는 칸의 값."""
    for upto, v in steps:
        if upto is None or value <= float(upto):
            return float(v)
    return float(steps[-1][1])


def property_tax_home(official_krw: int, one_home: bool, table: dict[str, Any], urban: bool = True) -> RuleResult:
    """주택 재산세 한 해치(지방세법 §110·§111·§111의2·§112·§151). one_home: 1세대 1주택."""
    if official_krw <= 0:
        return RuleResult(None, Status.UNKNOWN, "holding.property.none", [])
    ratio = _step(official_krw, table["ratio_one_home"]) if one_home else float(table["ratio"])
    base = official_krw * ratio / 100
    special = one_home and official_krw <= int(table["one_home_rate_max_krw"])
    tax = _progressive(base, table["rates_one_home"] if special else table["rates"])
    urban_tax = base * float(table["urban_rate"]) / 100 if urban else 0.0
    edu = tax * float(table["edu_rate_of_tax"]) / 100
    total = int(round(tax + urban_tax + edu, -3))
    ev = [{"official_krw": official_krw, "ratio_pct": ratio, "base_krw": int(base), "special_rate": special}]
    return RuleResult(
        {"total_krw": total, "tax_krw": int(tax), "urban_krw": int(urban_tax), "edu_krw": int(edu),
         "base_krw": int(base), "ratio_pct": ratio, "special_rate": special},
        Status.ESTIMATED, "holding.property", ev,
    )  # fmt: skip


def comprehensive_tax_home(
    official_total_krw: int, one_home: bool, homes: int, table: dict[str, Any], prop: dict[str, Any] | None
) -> RuleResult:
    """주택 종합부동산세 한 해치(종합부동산세법 §8·§9, 농특세 20%). official_total_krw: 가진 집 공시가격 합계.

    재산세 중복분은 「재산세 × 종부세 과세표준 ÷ 재산세 과세표준」으로 어림해 뺌(비율이 같을 때의 법정 산식과 같음)."""
    deduct = int(table["deduct_one_home_krw"] if one_home else table["deduct_krw"])
    if official_total_krw <= deduct:
        return RuleResult({"total_krw": 0, "base_krw": 0}, Status.ESTIMATED, "holding.comprehensive.none", [])
    base = (official_total_krw - deduct) * float(table["ratio"]) / 100
    rates = table["rates_three_plus"] if homes >= 3 else table["rates"]
    tax = _progressive(base, rates)
    if prop and prop.get("base_krw"):
        tax -= min(float(prop["tax_krw"]), float(prop["tax_krw"]) * base / float(prop["base_krw"]))
    tax = max(tax, 0.0)
    farm = tax * float(table["farm_rate_of_tax"]) / 100
    total = int(round(tax + farm, -3))
    return RuleResult(
        {"total_krw": total, "tax_krw": int(tax), "farm_krw": int(farm), "base_krw": int(base)},
        Status.ESTIMATED, "holding.comprehensive",
        [{"official_total_krw": official_total_krw, "deduct_krw": deduct, "homes": homes}],
    )  # fmt: skip


# 다른 집 값이 붙은 것 거르기(11/11): 면적이 이만큼 넘게 다르거나, 감정가와 견줘 이 밖이면 이 집 값이 아님
# (다른 동·상가동의 같은 호수, 집 전체 값이 붙은 지분 물건). 법 숫자가 아니라 자료 맞추기 기준이라 여기 둠.
AREA_GAP_M2 = 3.0
RATIO_MIN, RATIO_MAX = 0.2, 1.5


def official_price(
    kind: str,
    payload: dict[str, Any] | None,
    area_m2: float | None = None,
    appraisal_krw: int | None = None,
) -> dict[str, Any] | None:
    """브이월드 원문(raw.official_price_raw) → {'krw', 'year'} (공동주택·개별주택: 한 집 값, 땅: ㎡당).
    면적·감정가를 주면 이 집 값이 맞는지 보고, 아니면 None(틀린 세금을 보이느니 안 보임)."""
    items = (payload or {}).get("items") or []
    if not items:
        return None
    it = items[0]
    v = it.get("pblntfPclnd") if kind == "land" else it.get("pblntfPc") or it.get("housePc")
    try:
        krw = int(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return None
    if krw <= 0:
        return None
    if kind == "apt" and area_m2:
        try:
            own = float(str(it.get("prvuseAr") or "").replace(",", ""))
        except ValueError:
            own = 0.0
        if own and abs(own - area_m2) > AREA_GAP_M2:
            return None
    if kind != "land" and appraisal_krw and not RATIO_MIN <= krw / appraisal_krw <= RATIO_MAX:
        return None
    return {"krw": krw, "year": int(it.get("stdrYear") or (payload or {}).get("year") or 0)}
