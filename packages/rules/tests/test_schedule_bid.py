from datetime import date

from aucs_rules.bid_form_check import check, korean_amount
from aucs_rules.schedule import add_months, after_sale

D = date
HOL = [D(2026, 12, 25), D(2027, 1, 1), D(2027, 2, 8), D(2027, 2, 9)]


def _row(rows: list[dict], key: str) -> dict:
    return next(r for r in rows if r["key"] == key)


def test_add_months_clamps_month_end() -> None:
    assert add_months(D(2027, 1, 31), 1) == D(2027, 2, 28)
    assert add_months(D(2026, 11, 30), 6) == D(2027, 5, 30)


def test_schedule_legal_dates() -> None:
    # 2026-11-17(화) 매각 → 결정 11-24(화) → 항고 끝 12-01(화) → 확정 12-02
    v = after_sale(D(2026, 11, 17), HOL).value
    rows = v["rows"]
    assert _row(rows, "decide")["start"] == "2026-11-24"
    assert _row(rows, "appeal")["end"] == "2026-12-01"
    assert _row(rows, "pay_window")["start"] == "2026-12-02"
    assert _row(rows, "pay")["start"] == "2026-12-23"  # 확정 + 21일
    assert _row(rows, "tax")["start"] == "2027-02-22"  # 12-23 + 60 = 2-21(일) → 2-22(월)
    assert _row(rows, "order_deadline")["start"] == "2027-06-23"
    assert v["pay_estimated"] is True


def test_schedule_holiday_shifts_and_flags() -> None:
    # 결정기일이 휴일(12-25 금)에 걸리면 앞당겨 12-24
    v = after_sale(D(2026, 12, 18), HOL, pay_date=D(2027, 1, 20), flags=["farmland"]).value
    assert _row(v["rows"], "decide")["start"] == "2026-12-24"
    assert any(r["key"] == "farmland" for r in v["rows"])
    assert v["summary"]["pay"] == "2027-01-20"


def test_korean_amount() -> None:
    assert korean_amount(412_000_000) == "사억일천이백만원"
    assert korean_amount(1_005_000) == "일백만오천원"


def test_bid_form_levels() -> None:
    assert check(99, 100).value["level"] == "block"
    assert check(150, 100).value["level"] == "ok"
    assert check(1_504_000_000, 150_400_000).value["level"] == "stop"
    assert (
        check(300_000_000, 280_000_000, deposit_rate_pct=20, resale=True).value["deposit_krw"]
        == 56_000_000
    )
