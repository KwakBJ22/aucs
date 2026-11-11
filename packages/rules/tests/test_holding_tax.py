"""주택 보유세 어림 (TAX-02)."""

from aucs_rules.holding_tax import (
    _progressive,
    comprehensive_tax_home,
    official_price,
    property_tax_home,
)

P = {"ratio": 60, "ratio_one_home": [[300000000, 43], [600000000, 44], [None, 45]],
     "rates": [[60000000, 0.1], [150000000, 0.15], [300000000, 0.25], [None, 0.4]],
     "rates_one_home": [[60000000, 0.05], [150000000, 0.1], [300000000, 0.2], [None, 0.35]],
     "one_home_rate_max_krw": 900000000, "urban_rate": 0.14, "edu_rate_of_tax": 20}  # fmt: skip
C = {"deduct_krw": 900000000, "deduct_one_home_krw": 1200000000, "ratio": 60,
     "rates": [[300000000, 0.5], [600000000, 0.7], [1200000000, 1.0], [2500000000, 1.3],
               [5000000000, 1.5], [9400000000, 2.0], [None, 2.7]],
     "rates_three_plus": [[300000000, 0.5], [600000000, 0.7], [1200000000, 1.0], [2500000000, 2.0],
                          [5000000000, 3.0], [9400000000, 4.0], [None, 5.0]],
     "farm_rate_of_tax": 20}  # fmt: skip


def test_progressive_matches_published_steps() -> None:
    # 일반 주택: 과세표준 3억 → 57만 원(법정 누진 공제 표와 같음)
    assert round(_progressive(300_000_000, P["rates"])) == 570_000
    # 1세대1주택 특례: 3억 → 42만 원
    assert round(_progressive(300_000_000, P["rates_one_home"])) == 420_000


def test_property_tax_one_home_vs_general() -> None:
    one = property_tax_home(500_000_000, True, P).value
    gen = property_tax_home(500_000_000, False, P).value
    assert one["ratio_pct"] == 44 and one["special_rate"] is True
    assert gen["ratio_pct"] == 60 and gen["special_rate"] is False
    assert one["total_krw"] < gen["total_krw"]


def test_comprehensive_only_over_deduct() -> None:
    assert comprehensive_tax_home(1_100_000_000, True, 1, C, None).value["total_krw"] == 0
    prop = property_tax_home(2_000_000_000, False, P).value
    r = comprehensive_tax_home(2_000_000_000, False, 2, C, prop).value
    assert r["base_krw"] == 660_000_000 and r["total_krw"] > 0


def test_official_price_reads_vworld() -> None:
    apt = {"items": [{"pblntfPc": "261000000", "stdrYear": "2026"}]}
    land = {"items": [{"pblntfPclnd": "8758000", "stdrYear": "2026"}]}
    assert official_price("apt", apt) == {"krw": 261000000, "year": 2026}
    assert official_price("land", land) == {"krw": 8758000, "year": 2026}
    assert official_price("apt", {"items": []}) is None
