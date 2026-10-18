from datetime import date

from aucs_rules.payout import NamedTenant, payout
from aucs_rules.rights import Right
from aucs_rules.tenants import Tenant

D = date
TABLE = [
    {"valid_from": D(2023, 2, 21), "valid_to": None, "region_class": "seoul",
     "deposit_limit_krw": 165_000_000, "amount_krw": 55_000_000},
]  # fmt: skip


def test_senior_tenant_partly_paid_rest_assumed():
    # 임차인 전입 2023-01-01·확정 2023-01-01, 근저당 2023-06-01 → 대항력 있음, 배당요구함
    rights = [
        Right("을", "1", "근저당권설정", D(2023, 6, 1), amount_krw=300_000_000, holder="은행"),
        Right("갑", "5", "임의경매개시결정", D(2025, 1, 1)),
    ]
    t = Tenant(
        D(2023, 1, 1), fixed_date=D(2023, 1, 1), claim_date=D(2025, 2, 1), deposit_krw=400_000_000
    )
    r = payout(
        300_000_000, rights, [NamedTenant("김○○", t)], D(2023, 6, 1), D(2025, 3, 1), "seoul", TABLE
    )
    ten = r["tenants"][0]
    # 비용 200만 뒤 임차인이 먼저(2023-01-02) → 2억 9,800만 받고 1억 200만 떠안음
    assert ten["received_krw"] == 298_000_000
    assert ten["assume_krw"] == 102_000_000
    assert r["rows"][0]["name"] == "경매비용(대략)"


def test_small_lease_gets_top_priority():
    rights = [
        Right("을", "1", "근저당권설정", D(2023, 3, 1), amount_krw=500_000_000, holder="은행")
    ]
    t = Tenant(
        D(2024, 1, 1), claim_date=D(2025, 2, 1), deposit_krw=50_000_000
    )  # 후순위·확정일자 없음
    r = payout(
        400_000_000, rights, [NamedTenant("이○○", t)], D(2023, 3, 1), D(2025, 3, 1), "seoul", TABLE
    )
    ten = r["tenants"][0]
    assert ten["received_krw"] == 50_000_000 and ten["assume_krw"] == 0 and ten["power"] is False


def test_unclaimed_senior_tenant_assumes_all_and_seizure_unknown():
    rights = [
        Right("을", "1", "근저당권설정", D(2023, 6, 1), amount_krw=100_000_000, holder="은행"),
        Right("갑", "7", "압류", D(2024, 1, 1), holder="용인시"),
    ]
    t = Tenant(D(2023, 1, 1), deposit_krw=200_000_000)
    r = payout(
        300_000_000, rights, [NamedTenant("박○○", t)], D(2023, 6, 1), D(2025, 3, 1), "seoul", TABLE
    )
    assert r["tenants"][0]["assume_krw"] == 200_000_000
    assert r["unknown"] == ["압류 · 용인시"]
