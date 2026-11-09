from datetime import date

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
    d = date(2026, 11, 8)
    sql, p = match_sql({"sigungu": ["강남구"], "max_cash": 30_000_000}, d)
    assert "any(%(sigungu)s)" in sql and p == {
        "today": d,
        "sigungu": ["강남구"],
        "max_cash": 30_000_000,
        "homes_key": "0",  # 필요한 현금은 가진 집 수별(11/9) — 알림 조건엔 없으니 무주택
    }
    assert (
        "display_policy = 'public'" in sql and "a.result is not null" in sql
    )  # 보이는 물건만(11/8)
    assert match_sql({}, d)[1] == {"today": d}
    sql, p = match_sql({"usage": ["apt"], "exclude": ["share", "lien"], "rate_max": 80}, d)
    assert (
        p["usage_re"] == "(아파트)"
        and p["ex_rules"] == ["risk.share", "risk.lien"]
        and p["rate_max"] == 80
    )


def test_listing_gone_text():
    assert change_text("x", Change("listing", "listed", "gone"))[0] == "x 법원 목록에서 빠졌어요"
    assert "다시" in change_text("x", Change("listing", "gone", "listed"))[0]


def test_onbid_match_sql():
    from aucs_workers.jobs.notify import onbid_match_sql

    d = date(2026, 11, 8)
    assert onbid_match_sql({"source": "court"}, d) is None
    sql, p = onbid_match_sql(
        {"sigungu": ["강남구"], "max_cash": 5000, "usage": ["apt"], "exclude": ["share"]}, d
    )  # type: ignore[misc]
    assert "split_part(o.sigungu" in sql and "o.kind <> 'trust'" in sql
    assert p["sigungu"] == ["강남구"] and p["max_cash"] == 5000 and p["usage_re"] == "(아파트)"


def test_change_text_onbid():
    from aucs_workers.jobs.notify import Change, change_text

    t, _ = change_text("강남구 아파트", Change("listing", "listed", "gone"), onbid=True)
    assert "온비드" in t
    t, _ = change_text("강남구 아파트", Change("result", None, "낙찰"), onbid=True)
    assert t == "강남구 아파트 공매 낙찰"


def test_mock_text():
    from aucs_workers.jobs.notify import mock_text

    assert (
        mock_text("강남구 A", 500_000_000, "bid", "sold", 480_000_000)[0]
        == "강남구 A 내 금액이면 낙찰이었어요"
    )
    t = mock_text("강남구 A", 450_000_000, "bid", "sold", 480_000_000)
    assert t[0] == "강남구 A 3,000만원 모자랐어요"
    assert mock_text("강남구 A", None, "skip", "failed", None) is None
    assert "낙찰됐을" in mock_text("강남구 A", 300_000_000, "bid", "failed", None)[1]
