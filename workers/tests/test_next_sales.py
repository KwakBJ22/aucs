"""유찰 뒤 기일내역 → 다음 회차(11/4)."""

from datetime import date

from aucs_workers.extract.case_docs import detail_schedule, next_sales, past_failed_rounds

SCHED = {
    "dlt_dxdyDtsLst": [
        {"dxdyRslt": "유찰", "dxdyTime": "2026.09.30(10:00)", "dspslGdsSeq": "1",
         "tsLwsDspslPrc": "242,000,000원", "auctnDxdyKndNm": "매각기일"},
        {"dxdyRslt": "", "dxdyTime": "2026.11.04(10:00)", "dspslGdsSeq": "1",
         "tsLwsDspslPrc": "169,400,000원", "auctnDxdyKndNm": "매각기일"},
        {"dxdyRslt": "", "dxdyTime": "2026.11.11(15:30)", "dspslGdsSeq": "1",
         "tsLwsDspslPrc": "", "auctnDxdyKndNm": "매각결정기일"},
    ]
}  # fmt: skip


def test_next_sale_after_failure() -> None:
    got = next_sales(SCHED, date(2026, 10, 10))
    assert got == {1: {"date": date(2026, 11, 4), "min_price_krw": 169_400_000, "failed_count": 1}}


def test_past_next_date_ignored() -> None:
    assert next_sales(SCHED, date(2026, 11, 5)) == {}


def test_detail_schedule_gives_next_round() -> None:
    """물건상세 기일 목록만으로 다음 회차를 앎(11/7 — 기일내역 요청 생략)."""
    detail = {"dma_result": {"gdsDspslDxdyLst": [
        {"dxdyYmd": "20261013", "tsLwsDspslPrc": 164352000, "auctnDxdyKndCd": "01", "auctnDxdyRsltCd": "002"},
        {"dxdyYmd": "20261117", "tsLwsDspslPrc": 131482000, "auctnDxdyKndCd": "01", "auctnDxdyRsltCd": None},
        {"dxdyYmd": "20261124", "tsLwsDspslPrc": 0, "auctnDxdyKndCd": "02", "auctnDxdyRsltCd": None},
    ]}}  # fmt: skip
    got = next_sales(detail_schedule(detail, 1), date(2026, 11, 7))
    assert got == {1: {"date": date(2026, 11, 17), "min_price_krw": 131482000, "failed_count": 1}}


def test_past_failed_rounds() -> None:
    """11/8: 지난 유찰 회차를 빠짐없이(그 전 유찰 횟수와 같이)."""
    two = {"dlt_dxdyDtsLst": [
        {"dxdyRslt": "유찰", "dxdyTime": "2026.08.26(10:00)", "dspslGdsSeq": "1",
         "tsLwsDspslPrc": "345,714,286원", "auctnDxdyKndNm": "매각기일"},
        *SCHED["dlt_dxdyDtsLst"],
    ]}  # fmt: skip
    got = past_failed_rounds(two)
    assert [(x["date"], x["min_price_krw"], x["failed_before"]) for x in got] == [
        (date(2026, 8, 26), 345_714_286, 0),
        (date(2026, 9, 30), 242_000_000, 1),
    ]
