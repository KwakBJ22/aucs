from datetime import date

from aucs_api.services.pro import build_where, to_csv


def test_build_where_binds_everything():
    sql, p = build_where(
        {"sigungu": ["강남구"], "usage": ["apt", "villa", "zzz"], "failed_min": 1, "rate_max": 70,
         "days_max": 14, "exclude": ["share", "fatal"], "q": "푸르지오"},
        date(2026, 10, 19),
    )  # fmt: skip
    assert "any(%(sigungu)s)" in sql and p["usage_re"] == "(아파트)|(다세대|연립|빌라)"
    assert p["ex_rules"] == ["risk.share"] and "'fatal'" in sql
    assert p["q"] == "%푸르지오%" and "푸르지오" not in sql


def test_csv_has_bom_and_header():
    out = to_csv([{"court": "수원", "case_no": "2025타경55580", "min_price_krw": 710500000}])
    assert out.startswith("﻿법원,사건번호")
    assert "710500000" in out
