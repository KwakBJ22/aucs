"""세금이 대항력 임차인보다 먼저일 수 있는가 (11/11 강사판 반영)."""

from datetime import date

from aucs_rules.risk import signals
from aucs_rules.tenants import Tenant, base_date_of, tax_before_tenant

BASE = date(2022, 5, 4)  # 말소기준 근저당
T = Tenant(move_in_date=date(2021, 3, 2), fixed_date=date(2021, 3, 2), deposit_krw=200_000_000)


def test_base_date_of() -> None:
    assert base_date_of("2022.05.04. 근저당권") == BASE
    assert base_date_of("2023.6.2. 가압류") == date(2023, 6, 2)
    assert base_date_of("없음") is None


def test_tax_within_six_months_is_high() -> None:
    r = tax_before_tenant([T], BASE, [date(2021, 7, 1)])
    assert r.value == "high"


def test_tax_long_after_is_still_mid_not_safe() -> None:
    # 압류·교부청구가 몇 년 뒤라도 법정기일은 앞설 수 있음 → 「안전」이 아니라 「주의」
    assert tax_before_tenant([T], BASE, [date(2025, 9, 1)]).value == "mid"


def test_no_power_or_no_fixed_date_or_no_tax() -> None:
    late = Tenant(move_in_date=date(2023, 1, 1), fixed_date=date(2023, 1, 1), deposit_krw=1)
    assert tax_before_tenant([late], BASE, [date(2023, 2, 1)]).value is None  # 대항력 없음
    nofix = Tenant(move_in_date=date(2021, 3, 2), deposit_krw=1)
    assert tax_before_tenant([nofix], BASE, [date(2021, 4, 1)]).value is None  # 확정일자 없음
    assert tax_before_tenant([T], BASE, []).value is None  # 세금 교부청구 없음


def test_signal_level_follows_rule() -> None:
    s = [x for x in signals({"tax_before_tenant": "mid"}) if x.rule_id == "risk.tax_first"]
    assert s and s[0].level == "mid"
