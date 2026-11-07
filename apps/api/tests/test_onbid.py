from datetime import date, datetime, timedelta, timezone

from aucs_api.services.onbid import build_query, merge, onbid_card
from aucs_api.services.onbid_detail import checklist, rounds_view, trade_type

KST = timezone(timedelta(hours=9))
END = datetime(2026, 6, 24, 17, 0, tzinfo=KST)
ROW = {
    "item_id": "OB-2023-05662-001", "mng_no": "2023-05662-001", "kind": "seized", "kind_name": "압류재산",
    "usage_name": "아파트", "sigungu": "평택시", "dong": "통복동", "building_m2": 76.26, "land_m2": None,
    "appraisal_krw": 242_000_000, "min_price_krw": 169_400_000, "failed_count": 3, "bid_end": END,
    "next_round": {"min_price_krw": 145_200_000, "bid_end": "2026-07-01T17:00:00+09:00"},
}  # fmt: skip


def test_card() -> None:
    c = onbid_card(ROW, date(2026, 6, 22))
    assert c["source"] == "onbid" and c["case_no"] == "2023-05662-001" and c["kind_name"] == "압류"
    assert c["d_day"] == 2 and c["sale_date"] == "2026-06-24" and c["min_rate"] == 70
    assert c["deposit_krw"] == 16_940_000 and c["next_round"]["min_price_krw"] == 145_200_000
    assert (
        c["top_signal"] is None
        and onbid_card({**ROW, "kind": "trust"}, date(2026, 6, 22))["top_signal"]
    )


def test_card_undecided() -> None:
    c = onbid_card({**ROW, "bid_end": None, "next_round": None}, date(2026, 6, 22))
    assert c["d_day"] is None and c["sale_date"] is None and c["next_round"] is None


def test_query() -> None:
    assert (
        build_query(
            sigungu=[], max_cash=None, q="2025타경55580", extra=None, today=date(2026, 6, 22)
        )
        is None
    )
    sql, p = build_query(
        sigungu=[], max_cash=None, q="2023-05662-001", extra=None, today=date(2026, 6, 22)
    ) or ("", {})
    assert "o.mng_no = %(mng)s" in sql and p["mng"] == "2023-05662-001"
    sql, p = build_query(sigungu=["수원시"], max_cash=150_000_000, q=None,
                         extra={"days_max": 3, "exclude": ["share"]}, today=date(2026, 6, 22)) or ("", {})  # fmt: skip
    assert "split_part(o.sigungu" in sql and "o.kind <> 'trust'" in sql and p["days_max"] == 3


def test_merge() -> None:
    a = {"item_id": "a", "sale_date": "2026-06-30", "min_rate": 80}
    b = {"item_id": "b", "sale_date": "2026-06-24", "min_rate": 70}
    n = {"item_id": "n", "sale_date": None, "min_rate": None}
    assert [x["item_id"] for x in merge([a], [n, b], "deadline", 10)] == ["b", "a", "n"]
    assert [x["item_id"] for x in merge([a], [n, b], "rate", 2)] == ["b", "a"]


def test_rounds_view() -> None:
    rounds = [
        {"bid_start": END - timedelta(days=9), "bid_end": END - timedelta(days=7), "open_at": None, "min_price_krw": 193_600_000},
        {"bid_start": END - timedelta(days=2), "bid_end": END, "open_at": None, "min_price_krw": 169_400_000},
        {"bid_start": END + timedelta(days=5), "bid_end": END + timedelta(days=7), "open_at": None, "min_price_krw": 145_200_000},
    ]  # fmt: skip
    past = [{"opened_at": END - timedelta(days=6), "min_price_krw": 193_600_000, "result": "유찰"}]
    v = rounds_view(rounds, past, END, 242_000_000)
    assert [x["label"] for x in v] == ["지난", "이번", "다음"]
    assert [x["rate"] for x in v] == [80, 70, 60]


def test_misc() -> None:
    assert trade_type("아파트", None) == "apt" and trade_type(None, "… 다세대주택") == "rowhouse"
    assert trade_type("대지", "토지") is None
    ck = {x["key"]: x["state"] for x in checklist("seized")}
    assert ck["tenant"] == "공매엔 없어요" and ck["trust"] == "해당 없음"
    assert {x["key"]: x["state"] for x in checklist("trust")}["trust"] == "전문가 확인 필요"


def test_notice_rows():
    from aucs_api.services.onbid_detail import notice_rows

    rows = notice_rows(
        {"bidDivNm": "전자입찰", "cptnMthodNm": "일반경쟁", "bidMthodNm": "최고가방식", "collbBidPsblYn": "N",
         "evcRsbyTrgtCont": "낙찰자", "orgNm": "주식회사 무궁화신탁"},
        {"onbidPbancNm": "제1차 공매", "pbancYmd": "20261012"},
    )  # fmt: skip
    d = {r["label"]: r["value"] for r in rows}
    assert d["입찰 방식"] == "전자입찰 · 일반경쟁 · 최고가방식"
    assert d["공고일"] == "2026-10-12" and d["공동 입찰"] == "안 돼요" and "대리 입찰" not in d
