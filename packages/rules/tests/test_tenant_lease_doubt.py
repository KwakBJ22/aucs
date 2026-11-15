from datetime import date

from aucs_rules.risk import signals
from aucs_rules.tenants import Tenant, claimed_in_time, priority_date, tenant_doubts

D = date


def test_lease_reg_before_start_counts_as_claimed():
    t = Tenant(D(2020, 1, 1), deposit_krw=100_000_000, has_lease_registration=True,
               lease_registration_date=D(2024, 3, 1))  # fmt: skip
    assert claimed_in_time(t, D(2025, 9, 1), D(2025, 6, 20)).value is True
    # 경매 시작 뒤에 한 임차권등기는 배당요구를 따로 해야 함
    late = Tenant(D(2020, 1, 1), has_lease_registration=True, lease_registration_date=D(2025, 7, 1))
    assert claimed_in_time(late, D(2025, 9, 1), D(2025, 6, 20)).value is False
    # 경매 시작일을 모르면 예전처럼
    assert claimed_in_time(t, D(2025, 9, 1), None).value is False


def test_lease_reg_gives_priority():
    t = Tenant(D(2020, 1, 1), has_lease_registration=True, lease_registration_date=D(2024, 3, 1))
    assert priority_date(t).value == D(2024, 3, 1)
    t2 = Tenant(D(2020, 1, 1), fixed_date=D(2020, 1, 1), has_lease_registration=True,
                lease_registration_date=D(2024, 3, 1))  # fmt: skip
    assert priority_date(t2).value == D(2020, 1, 2)


def test_doubt_docs_and_mortgage_is_high():
    t = Tenant(D(2018, 1, 2), deposit_krw=300_000_000)
    r = tenant_doubts([t], D(2019, 5, 10), True,
                      ["채권자 유OO 아파트 무상거주확인서 제출"], "", 400_000_000).value  # fmt: skip
    assert r["level"] == "high"
    assert r["reasons"][0].startswith("채권자가 「무상거주확인서」")
    assert any("근저당보다 먼저" in x for x in r["reasons"])
    sig = [s for s in signals({"tenant_doubt": r}) if s.rule_id == "risk.tenant_doubt"]
    assert sig and sig[0].level == "high" and sig[0].title.startswith("임차인이 진짜인지 확인 필요")


def test_doubt_ignores_lien_exclusion_and_powerless_tenant():
    late = Tenant(D(2023, 1, 2), deposit_krw=300_000_000)  # 말소기준 뒤 전입 → 낙찰자 짐 아님
    assert (
        tenant_doubts([late], D(2019, 5, 10), True, ["무상거주확인서 제출"], "", 4e8).value is None
    )
    t = Tenant(D(2018, 1, 2), deposit_krw=10_000_000, fixed_date=D(2018, 1, 2))
    assert (
        tenant_doubts([t], D(2019, 5, 10), False, ["유치권배제 신청서 제출"], "", 4e8).value is None
    )


def test_doubt_tentative_only_is_info():
    t = Tenant(D(2018, 1, 2), deposit_krw=10_000_000, fixed_date=D(2018, 1, 2))
    poss = "폐문 부재로 … 소유자 아닌 세대주 김OO 세대가 등재되어 있어 일응 임차인으로 기재함"
    r = tenant_doubts([t], D(2019, 5, 10), False, [], poss, 400_000_000).value
    assert r["level"] == "info" and len(r["reasons"]) == 1


def test_doubt_owner_listed_and_big_deposit():
    t = Tenant(D(2018, 1, 2), deposit_krw=380_000_000)
    poss = "채무자 겸 소유자 정OO가 주민등록상 세대주로 등재되어 있으나 점유관계는 미상임"
    r = tenant_doubts([t], D(2019, 5, 10), False, [], poss, 400_000_000).value
    assert "소유자도 같은 집에 세대주로 올라 있어요" in r["reasons"]
    assert "보증금이 집값의 90%를 넘어요" in r["reasons"]
    assert r["level"] == "high"  # 근거 3개 이상
