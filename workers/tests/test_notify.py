from aucs_workers.jobs.notify import Change, change_text, match_sql, watch_changes, won


def test_first_value_is_baseline_only():
    ch = watch_changes({}, {"sale_date": "2026-10-28", "min_price": "100000000", "result": None})
    assert [c.kind for c in ch] == ["sale_date", "min_price"]
    assert all(c.prev is None for c in ch)


def test_change_detected_and_same_ignored():
    prev = {"sale_date": "2026-10-28", "min_price": "100000000"}
    ch = watch_changes(
        prev, {"sale_date": "2026-12-02", "min_price": "100000000", "result": "failed"}
    )
    assert ch == [Change("sale_date", "2026-10-28", "2026-12-02"), Change("result", None, "failed")]


def test_texts():
    t, b = change_text("강남구 역삼동", Change("min_price", "100000000", "80000000"))
    assert t == "강남구 역삼동 최저가가 내렸어요" and b == "1억원 → 8,000만원"
    assert change_text("x", Change("result", "failed", "sold"))[0] == "x 매각"
    assert won(123_450_000) == "1억 2,345만원"


def test_match_sql():
    sql, p = match_sql({"sigungu": ["강남구"], "max_cash": 30_000_000})
    assert "any(%(sigungu)s)" in sql and p == {"sigungu": ["강남구"], "max_cash": 30_000_000}
    assert match_sql({})[1] == {}
