"""곧 나올 물건(11/27) — 순수 함수: 언제쯤 · 같은 단지 면적별 시세."""

from datetime import date

from aucs_api.services.upcoming import expect, lot_label, market_by_lot, timing_table


def test_timing_table_small_court_uses_all() -> None:
    rows = [{"court_code": "B000210", "days": d} for d in range(200, 400, 10)]  # 20건
    rows += [{"court_code": "B000252", "days": 500}] * 3  # 3건 — 표본 적음
    t = timing_table(rows, min_n=15)
    assert "B000210" in t and "B000252" not in t
    assert t["*"]["n"] == 23
    assert t["B000210"]["lo"] < t["B000210"]["hi"]


def test_expect_months_and_late() -> None:
    table = {"*": {"lo": 200, "hi": 400, "n": 100}}
    e = expect(date(2026, 9, 15), "B000210", table, date(2026, 11, 27))
    assert e == {"from": "2027-04", "to": "2027-10", "late": False, "court_wide": True}
    old = expect(date(2024, 1, 1), "B000210", table, date(2026, 11, 27))
    assert old is not None and old["late"]
    assert expect(None, "B000210", table, date(2026, 11, 27)) is None


def test_market_by_lot_top_two_by_count() -> None:
    rows = [
        {"region_code": "1162010200", "lot_no": "1421-1", "area": 84, "n": 2, "mid": 450_000_000},
        {"region_code": "1162010200", "lot_no": "1421-1", "area": 59, "n": 9, "mid": 310_000_000},
        {"region_code": "1162010200", "lot_no": "1421-1", "area": 114, "n": 1, "mid": 600_000_000},
    ]
    m = market_by_lot(rows)[("1162010200", "1421-1")]
    assert [x["area"] for x in m] == [59, 84]


def test_lot_label_cuts_at_lot_and_drops_sido() -> None:
    a = "경기도 안산시 단원구 와동 709-2 시온캐슬 4층401호"
    assert lot_label(a, "709-2") == "안산시 단원구 와동 709-2"
    assert lot_label("서울특별시 강서구 화곡동 1-1", None) == "강서구 화곡동 1-1"
