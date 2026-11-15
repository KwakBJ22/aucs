"""주택 임차인 판정 (주택임대차보호법 제3조·제3조의2·제8조).

개발 기준이며 출시 전 법률 전문가 검토 대상입니다. 상가 임차인은 2단계 별도 규칙.
"""

import re
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from aucs_rules.result import RuleResult, Status


@dataclass(frozen=True)
class Tenant:
    move_in_date: date | None
    fixed_date: date | None = None
    claim_date: date | None = None  # 배당요구일
    deposit_krw: int | None = None
    has_lease_registration: bool = False
    lease_registration_date: date | None = None
    relation_text: str = ""  # 현황조사서·명세서의 관계 글
    verified: bool = False


def opposing_power(t: Tenant, base_date: date | None) -> RuleResult:
    """대항력: 전입 다음 날 0시에 생김 → 전입일이 말소기준 접수일보다 하루 이상 앞서야 함 (제3조 제1항)."""
    effective = t.move_in_date
    if t.has_lease_registration and t.lease_registration_date:
        effective = min(x for x in [t.move_in_date, t.lease_registration_date] if x)
    if effective is None or base_date is None:
        return RuleResult(None, Status.UNKNOWN, "tenants.opposing.missing", [])
    has = effective < base_date
    ev = [{"move_in_date": str(effective), "base_date": str(base_date)}]
    return RuleResult(
        has, Status.CONFIRMED if t.verified else Status.ESTIMATED, "tenants.opposing", ev
    )


def priority_date(t: Tenant) -> RuleResult:
    """우선변제 순위일 = 대항력 발생일(전입 다음 날)과 확정일자 중 늦은 날 (제3조의2 제2항).

    임차권등기가 있으면 그 등기로도 우선변제권이 생김(제3조의3 제5항) → 둘 중 빠른 날."""
    cand = []
    if t.move_in_date and t.fixed_date:
        cand.append(max(t.move_in_date + timedelta(days=1), t.fixed_date))
    if t.has_lease_registration and t.lease_registration_date:
        cand.append(t.lease_registration_date)
    if not cand:
        return RuleResult(None, Status.UNKNOWN, "tenants.priority.missing", [])
    d = min(cand)
    return RuleResult(d, Status.ESTIMATED, "tenants.priority", [{"priority_date": str(d)}])


_BASE_DATE = re.compile(r"(\d{4})\s*\.\s*(\d{1,2})\s*\.\s*(\d{1,2})")
TAX_NEAR_DAYS = 183  # 기준일 뒤 6개월 안 교부청구는 법정기일이 앞설 가능성이 매우 높음


def base_date_of(text: str | None) -> date | None:
    """명세서 「최선순위 설정」 글(「2022.05.04. 근저당권」) → 날짜. 못 읽으면 None."""
    m = _BASE_DATE.search(text or "")
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def tax_before_tenant(
    tenants: list[Tenant], base_date: date | None, tax_dates: list[date]
) -> RuleResult:
    """세금이 대항력 임차인보다 먼저 배당될 수 있는가 (11/11 강사판 반영).

    세금과 임차보증금의 순위는 압류·교부청구일이 아니라 세금의 「법정기일」로 정함(국세기본법 §35①3·②,
    지방세기본법 §71). 법정기일은 압류보다 훨씬 앞설 수 있어 문건만으로는 모름 → 대항력·확정일자 있는 임차인이 있고
    세금 교부청구가 하나라도 있으면, 법정기일을 확인할 때까지 세금이 먼저라고 봄.
    임차인 기준일(전입 다음 날과 확정일자 중 늦은 날) 전이거나 그 뒤 6개월 안이면 「high」, 그보다 늦으면 「mid」.
    대항력 있는 임차인은 배당받지 못한 잔액을 낙찰자에게 주장함(대법원 97다11195).
    """
    if not tax_dates:
        return RuleResult(None, Status.ESTIMATED, "tenants.tax_first.none", [])
    level: str | None = None
    ev: list[dict[str, Any]] = []
    for t in tenants:
        if not t.deposit_krw:
            continue
        if opposing_power(t, base_date).value is not True:
            continue
        p = priority_date(t).value
        if not isinstance(p, date):
            continue  # 확정일자가 없으면 배당 순위가 없어 세금과 견줄 일이 없음(보증금은 이미 인수 신호)
        near = any((d - p).days <= TAX_NEAR_DAYS for d in tax_dates)
        lv = "high" if near else "mid"
        level = "high" if "high" in (level, lv) else lv
        ev.append({"tenant_date": str(p), "tax_dates": sorted(str(d) for d in tax_dates)[:5]})
    if level is None:
        return RuleResult(None, Status.ESTIMATED, "tenants.tax_first.no_tenant", [])
    return RuleResult(level, Status.NEEDS_CHECK, "tenants.tax_first", ev)


def lease_reg_before_start(t: Tenant, auction_start: date | None) -> bool:
    """경매개시결정 등기 전에 임차권등기를 마쳤는지 — 그러면 배당요구 없이도 배당받음
    (민사집행법 제148조 제3호 「첫 경매개시결정등기 전에 등기된 권리자」, 대법원 2005다33039)."""
    return bool(
        t.has_lease_registration
        and t.lease_registration_date
        and auction_start
        and t.lease_registration_date < auction_start
    )


def claimed_in_time(
    t: Tenant, claim_deadline: date | None, auction_start: date | None = None
) -> RuleResult:
    """배당요구종기 안에 배당요구했는지. 경매 전 임차권등기는 요구한 것으로 봄."""
    if lease_reg_before_start(t, auction_start):
        return RuleResult(True, Status.ESTIMATED, "tenants.claim.lease_reg",
                          [{"lease_registration_date": str(t.lease_registration_date),
                            "auction_start": str(auction_start)}])  # fmt: skip
    if t.claim_date is None:
        return RuleResult(False, Status.ESTIMATED, "tenants.claim.none", [])
    if claim_deadline is None:
        return RuleResult(None, Status.UNKNOWN, "tenants.claim.no_deadline", [])
    return RuleResult(t.claim_date <= claim_deadline, Status.ESTIMATED, "tenants.claim", [])


def small_lease_amount(
    t: Tenant,
    region_class: str,
    first_security_date: date | None,
    auction_start_date: date | None,
    house_value_krw: int | None,
    table: list[dict[str, Any]],
) -> RuleResult:
    """최우선변제 금액 (제8조, 시행령 제10조·제11조).

    table: ref.rule_tables 'small_lease_limit' 행들
      [{"valid_from": date, "valid_to": date|None, "region_class": str, "deposit_limit_krw": int, "amount_krw": int}]
    기준일 = 최초 담보물권 설정일. 경매개시결정 등기 전에 대항요건을 갖춰야 함. 주택가액의 1/2 한도.
    """
    if t.deposit_krw is None or first_security_date is None:
        return RuleResult(0, Status.UNKNOWN, "tenants.small.missing", [])
    if auction_start_date and t.move_in_date and t.move_in_date >= auction_start_date:
        return RuleResult(0, Status.ESTIMATED, "tenants.small.after_start", [])
    rows = [
        r for r in table
        if r["region_class"] == region_class and r["valid_from"] <= first_security_date
        and (r.get("valid_to") is None or first_security_date <= r["valid_to"])
    ]  # fmt: skip
    if not rows:
        return RuleResult(0, Status.NEEDS_CHECK, "tenants.small.no_table", [])
    row = max(rows, key=lambda r: r["valid_from"])
    if t.deposit_krw > row["deposit_limit_krw"]:
        return RuleResult(0, Status.ESTIMATED, "tenants.small.over_limit", [row])
    amount = min(t.deposit_krw, row["amount_krw"])
    if house_value_krw is not None:
        amount = min(amount, house_value_krw // 2)
    return RuleResult(amount, Status.ESTIMATED, "tenants.small", [row])


def assumed_amount(
    t: Tenant, has_power: bool | None, claimed: bool | None, received_krw: int
) -> RuleResult:
    """낙찰자가 떠안는 보증금: 대항력 있으면 배당으로 못 받는 나머지, 배당요구 안 했으면 전액."""
    if has_power is None or t.deposit_krw is None:
        return RuleResult(None, Status.NEEDS_CHECK, "tenants.assumed.unknown", [])
    if not has_power:
        return RuleResult(0, Status.ESTIMATED, "tenants.assumed.none", [])
    if not claimed:
        return RuleResult(t.deposit_krw, Status.ESTIMATED, "tenants.assumed.full", [])
    return RuleResult(
        max(t.deposit_krw - received_krw, 0), Status.ESTIMATED, "tenants.assumed.rest", []
    )


_FAMILY = re.compile(
    r"(부|모|부친|모친|아들|딸|자녀|배우자|처|남편|형|누나|언니|오빠|동생|형제|자매|사위|며느리|손자|손녀|시부모|장인|장모)"
)


def family_tenant(t: Tenant) -> RuleResult:
    """현황조사서·명세서에 소유자·채무자와의 가족 관계 글이 있으면 주의."""
    m = _FAMILY.search(t.relation_text or "")
    if m:
        return RuleResult(True, Status.ESTIMATED, "tenants.family", [{"word": m.group(1)}])
    return RuleResult(
        False, Status.ESTIMATED if t.relation_text else Status.UNKNOWN, "tenants.family", []
    )


def flatten_small_lease_table(rule_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """ref.rule_tables 'small_lease_limit' 행(지역별 값 묶음) → small_lease_amount 가 읽는 줄들."""
    out = []
    for r in rule_rows:
        for region_class, v in r["value"].items():
            out.append({"valid_from": r["valid_from"], "valid_to": r.get("valid_to"), "region_class": region_class,
                        "deposit_limit_krw": v["deposit_limit_krw"], "amount_krw": v["amount_krw"]})  # fmt: skip
    return out


# ── 가짜 임차인 의심 (11/15 대표님) ─────────────────────────────
# 판정은 법원(배당이의·명도 소송)이 함 → 화면에는 「확인 필요」로만. 단정하는 말 쓰지 않음.
_DOC_DOUBT = re.compile(r"무상\s*거주|배당\s*(?:\((?:전부|일부)\))?\s*배제")
_TENTATIVE = re.compile(r"일응\s*임차인|점유\s*관계[는가]?\s*미상")
_OWNER_LISTED = re.compile(
    r"(?:채무자\s*겸\s*)?소유자\s*[가-힣○O]{0,10}(?:와|과)?.{0,15}세대주로\s*등재"
)


def tenant_doubts(
    tenants: list[Tenant],
    base_date: date | None,
    base_is_mortgage: bool,
    doc_texts: list[str],
    possession_text: str,
    price_krw: int | None,
) -> RuleResult:
    """임차인이 진짜인지 의심할 만한 근거 → {"level": high/mid/info, "reasons": [...]} 또는 None.

    낙찰자에게 짐이 되는 임차인(대항력 있음, 또는 날짜를 몰라 판단 못 함)이 있을 때만 봄.
    - 문건: 채권자의 「무상거주확인서」·「배당배제신청」 (가장 강함)
    - 근저당보다 먼저 들어온 임차인: 은행은 대출 때 다른 세입자가 없다는 확인서를 받음
    - 확정일자·배당요구 없이 보증금이 큼 / 보증금이 집값의 90% 넘음
    - 현황조사서: 소유자도 세대주로 올라 있음, 가족 관계, 만나지 못해 「일응」 임차인
    """
    risky = [t for t in tenants if opposing_power(t, base_date).value is not False]
    if not risky:
        return RuleResult(None, Status.ESTIMATED, "tenants.doubt.none", [])
    reasons: list[str] = []
    strong = any(_DOC_DOUBT.search(x or "") and "유치권" not in (x or "") for x in doc_texts)
    if strong:
        reasons.append("채권자가 「무상거주확인서」·「배당배제신청」을 냈어요")
    power = [t for t in risky if opposing_power(t, base_date).value is True]
    if base_is_mortgage and power:
        reasons.append(
            "근저당보다 먼저 들어온 임차인 — 대출 때 은행이 「무상거주확인서」를 받았을 수 있어요"
        )
    big = (price_krw or 0) * 0.3
    if any(t.fixed_date is None and t.claim_date is None and t.deposit_krw and big
           and t.deposit_krw >= big for t in power):  # fmt: skip
        reasons.append("확정일자·배당요구 없이 보증금이 커요")
    if price_krw and any(t.deposit_krw and t.deposit_krw >= price_krw * 0.9 for t in risky):
        reasons.append("보증금이 집값의 90%를 넘어요")
    if _OWNER_LISTED.search(possession_text or ""):
        reasons.append("소유자도 같은 집에 세대주로 올라 있어요")
    fam = [m.group(1) for t in risky if (m := _FAMILY.search(t.relation_text or ""))]
    if fam:
        reasons.append(f"소유자·채무자의 가족({fam[0]})으로 적혀 있어요")
    tentative = bool(_TENTATIVE.search(possession_text or ""))
    if tentative:
        reasons.append("조사 때 만나지 못해 「일응」 임차인으로 적혔어요 — 실제로 사는지 확인")
    if not reasons:
        return RuleResult(None, Status.ESTIMATED, "tenants.doubt.none", [])
    if strong or len(reasons) >= 3:
        level = "high"
    elif tentative and len(reasons) == 1:
        level = "info"  # 만나지 못한 것만으로는 약함
    else:
        level = "mid"
    return RuleResult({"level": level, "reasons": reasons}, Status.NEEDS_CHECK, "tenants.doubt", [])
