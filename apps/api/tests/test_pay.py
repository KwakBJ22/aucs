"""결제 전 · 후(11/23): 기간 · 주문 번호 · 이름 · 수단 한 줄 · 키 없을 때 잠김."""

import re
from datetime import date

import pytest
from aucs_api.services import pay
from fastapi import HTTPException


def test_month_ends_day_before_same_day_next_month() -> None:
    assert pay.period_end("month", date(2026, 11, 23)) == date(2026, 12, 22)
    assert pay.period_end("month", date(2026, 12, 15)) == date(2027, 1, 14)
    # 1/31 → 2월에 31일이 없으면 2월 마지막 날의 전날
    assert pay.period_end("month", date(2027, 1, 31)) == date(2027, 2, 27)


def test_year_ends_day_before_same_day_next_year() -> None:
    assert pay.period_end("year", date(2026, 11, 1)) == date(2027, 10, 31)  # 365일
    assert pay.period_end("year", date(2028, 2, 29)) == date(2029, 2, 27)


def test_one_until_day_after_sale() -> None:
    assert pay.period_end("one", date(2026, 11, 23), date(2026, 12, 3)) == date(2026, 12, 4)
    with pytest.raises(ValueError):
        pay.period_end("one", date(2026, 11, 23))


def test_order_id_fits_toss_rule() -> None:
    oid = pay.new_order_id(date(2026, 11, 23))
    assert 6 <= len(oid) <= 64
    assert re.fullmatch(r"[A-Za-z0-9_=-]+", oid)
    assert oid != pay.new_order_id(date(2026, 11, 23))


def test_order_name() -> None:
    assert pay.order_name("personal", "month") == "옥스경매 개인 · 매달"
    assert pay.order_name("personal", "year") == "옥스경매 개인 · 1년"
    assert pay.order_name("one", "one", "2025타경1234") == "옥스경매 한 건 · 2025타경1234"
    assert len(pay.order_name("one", "one", "가" * 200)) == 100


def test_method_note() -> None:
    assert pay.method_note({"method": "카드"}) == "카드"
    assert (
        pay.method_note({"method": "간편결제", "easyPay": {"provider": "토스페이"}})
        == "간편결제 · 토스페이"
    )
    assert pay.method_note({}) == "토스페이먼츠"


def test_closed_without_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pay.settings, "TOSS_CLIENT_KEY", "")
    monkeypatch.setattr(pay.settings, "TOSS_SECRET_KEY", "")
    assert not pay.is_open()
    with pytest.raises(HTTPException) as e:
        pay.make_order("u", "personal", "year", None, "card")
    assert e.value.status_code == 503
    assert pay.webhook({"eventType": "PAYMENT_STATUS_CHANGED"}) == {"ok": False}
    assert pay.renew_due() == {"open": False}


def test_basic_auth_has_colon(monkeypatch: pytest.MonkeyPatch) -> None:
    import base64

    monkeypatch.setattr(pay.settings, "TOSS_SECRET_KEY", "test_sk_abc")
    assert base64.b64decode(pay._auth().split()[1]) == b"test_sk_abc:"
