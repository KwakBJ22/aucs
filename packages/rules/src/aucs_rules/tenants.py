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
    """우선변제 순위일 = 대항력 발생일(전입 다음 날)과 확정일자 중 늦은 날 (제3조의2 제2항)."""
    if t.move_in_date is None or t.fixed_date is None:
        return RuleResult(None, Status.UNKNOWN, "tenants.priority.missing", [])
    d = max(t.move_in_date + timedelta(days=1), t.fixed_date)
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


def claimed_in_time(t: Tenant, claim_deadline: date | None) -> RuleResult:
    """배당요구종기 안에 배당요구했는지."""
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
