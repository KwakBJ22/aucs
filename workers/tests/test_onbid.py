from datetime import datetime

from aucs_workers.collectors.onbid_parse import (
    KST,
    current_round,
    kind_of,
    lot_from,
    parse_item,
    parse_result,
    to_dt,
)

# 원문 스킬(9/8 실측) 칸 이름으로 만든 한 줄
ITEM = {
    "cltrMngNo": "2023-05662-001",
    "pbctCdtnNo": "3412345",
    "onbidPbancNo": "901995",
    "cltrNm": "경기도 평택시 통복동 477 삼성아파트 제108동 제7층 제701호",
    "prptDivNm": "압류재산",
    "prptDivCd": "0007",
    "dspsMthodNm": "매각",
    "lctnSdnm": "경기도",
    "lctnSggnm": "평택시",
    "lctnEmdNm": "통복동",
    "apslEvlAmt": "242000000",
    "lowstBidPrcIndctCont": "169400000",
    "usbdNft": "3",
    "cltrBidBgngDt": "202606221000",
    "cltrBidEndDt": "202606241700",
    "pbctStatNm": "입찰진행중",
    "apslPrcCtrsLowstBidRto": None,
}


def test_dates() -> None:
    assert to_dt("202606241700") == datetime(2026, 6, 24, 17, 0, tzinfo=KST)
    assert to_dt("20260624") == datetime(2026, 6, 24, 0, 0, tzinfo=KST)
    assert to_dt("299901021600") is None and to_dt("999912310000") is None and to_dt("") is None


def test_kind() -> None:
    assert kind_of("압류재산") == "seized" and kind_of(None, "0007") == "seized"
    assert (
        kind_of("신탁재산") == "trust"
        and kind_of("국유재산") == "public"
        and kind_of("수탁재산") == "public"
    )
    assert kind_of("기타일반재산") == "general"


def test_lot() -> None:
    assert lot_from("경기도 광주시 오포읍 신현리 470-12 107동 201호", "신현리") == "470-12"
    assert lot_from("경기도 평택시 통복동 477 삼성아파트", "통복동") == "477"
    assert lot_from("경기도 양평군 강상면 산 12-3 외 2필지", "강상면") == "산12-3"
    assert lot_from("서울특별시 금천구 탑골로 54-3", "시흥동") is None


def test_item() -> None:
    p = parse_item(ITEM)
    assert p is not None
    assert p["item_id"] == "OB-2023-05662-001" and p["kind"] == "seized"
    assert (
        p["appraisal_krw"] == 242_000_000
        and p["min_price_krw"] == 169_400_000
        and p["failed_count"] == 3
    )
    assert p["dong"] == "통복동" and p["lot_no"] == "477"
    assert p["address"].startswith("경기도 평택시 통복동 477")
    assert p["bid_end"] == datetime(2026, 6, 24, 17, 0, tzinfo=KST)
    assert parse_item({"cltrNm": "번호 없음"}) is None


def test_item_undecided_schedule() -> None:
    p = parse_item({**ITEM, "cltrBidEndDt": "299901021600", "apslEvlAmt": None})
    assert p is not None and p["bid_end"] is None and p["appraisal_krw"] is None


def test_current_round() -> None:
    now = datetime(2026, 6, 23, 9, 0, tzinfo=KST)
    a = {"bid_end": datetime(2026, 6, 17, 17, 0, tzinfo=KST), "cond_no": "1"}
    b = {"bid_end": datetime(2026, 6, 24, 17, 0, tzinfo=KST), "cond_no": "2"}
    c = {"bid_end": datetime(2026, 7, 1, 17, 0, tzinfo=KST), "cond_no": "3"}
    assert current_round([a, c, b], now)["cond_no"] == "2"
    assert current_round([a], now)["cond_no"] == "1"
    assert current_round([{"bid_end": None, "cond_no": "9"}], now)["cond_no"] == "9"


def test_result_rate_from_prices() -> None:
    p = parse_result({
        "cltrMngNo": "2023-05662-001", "opbdDt": "202607021100", "onbidPbancNo": "1",
        "cltrNm": "경기도 평택시 통복동 477", "apslEvlAmt": "242000000",
        "lowstBidPrcIndctCont": "145200000", "scsbdAmt": "163680000", "vldBidrCnt": "13", "pbctStatNm": "낙찰",
    })  # fmt: skip
    assert p is not None and p["sido"] == "경기도" and p["bidders"] == 13
    assert p["rate_min"] == 112.73 and p["rate_appraisal"] == 67.64
    assert parse_result({"cltrMngNo": "x"}) is None


def test_result_code() -> None:
    from aucs_workers.collectors.onbid import _items, _result_code

    assert _result_code({"response": {"header": {"resultCode": "00", "resultMsg": "OK"}}}) == (
        "00",
        "OK",
    )
    assert (
        _result_code({"resultCode": "30", "resultMsg": "SERVICE_KEY_IS_NOT_REGISTERED_ERROR"})[0]
        == "30"
    )
    assert (
        _result_code({"OpenAPI_ServiceResponse": {"cmmMsgHeader": {"returnReasonCode": "30"}}})[0]
        == "30"
    )
    items, total = _items({"response": {"body": {"items": {"item": [{"a": 1}]}, "totalCount": 1}}})
    assert items == [{"a": 1}] and total == 1
    assert _items({"resultCode": "00"}) == ([], None)


def test_pnu_and_trust():
    from aucs_workers.collectors.onbid_parse import kind_of, lot_from_pnu

    assert lot_from_pnu("4127110300013090002") == "1309-2"
    assert lot_from_pnu("4183032000203220000") == "산322"
    assert lot_from_pnu("") is None
    assert kind_of("기타일반재산", "0005", "주식회사 무궁화신탁") == "trust"
    assert kind_of("기타일반재산", "0005", "농협은행주식회사") == "finance"
    assert kind_of("압류재산", "0007", "한국자산관리공사") == "seized"
