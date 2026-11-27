"""보증기관이 넘겨받은 보증금 — 원래 임차인과 한 사람(11/27 수원 2025타경51173: 3명 · 2억 9,600만 → 2명 · 1억 4,800만)."""

from datetime import date

from aucs_rules.tenants import Tenant, merge_guarantor, power_tenants


def test_guarantor_merged_into_tenant() -> None:
    rows = [
        {"name_raw": "정은나", "move_in_date": date(2022, 3, 7), "fixed_date": date(2022, 2, 17),
         "claim_date": None, "deposit_krw": 148_000_000, "monthly_rent_krw": None, "has_lease_registration": True},
        {"name_raw": "정형묵", "move_in_date": date(2024, 9, 13), "fixed_date": None,
         "claim_date": None, "deposit_krw": None, "monthly_rent_krw": None, "has_lease_registration": False},
        {"name_raw": "주택도시보증공사(정은나)", "move_in_date": date(2022, 3, 7), "fixed_date": date(2022, 2, 17),
         "claim_date": date(2025, 3, 14), "deposit_krw": 148_000_000, "monthly_rent_krw": None,
         "has_lease_registration": False},
    ]  # fmt: skip
    out = merge_guarantor(rows)
    assert len(out) == 2
    kim = out[0]
    assert kim["claim_date"] == date(2025, 3, 14) and kim["has_lease_registration"]
    ts = [Tenant(move_in_date=r["move_in_date"], claim_date=r["claim_date"], deposit_krw=r["deposit_krw"],
                 has_lease_registration=r["has_lease_registration"]) for r in out]  # fmt: skip
    tp = power_tenants(ts, date(2023, 1, 1))
    assert tp == {"n": 1, "deposit_krw": 148_000_000, "unclaimed": False, "lease_known": True}


def test_guarantor_alone_kept() -> None:
    rows = [{"name_raw": "시보증공사(윤소연)", "move_in_date": date(2021, 8, 6), "deposit_krw": 270_000_000}]
    assert merge_guarantor(rows) == rows
