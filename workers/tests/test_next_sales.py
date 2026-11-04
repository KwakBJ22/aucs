"""유찰 뒤 기일내역 → 다음 회차(11/4)."""

from datetime import date

from aucs_workers.extract.case_docs import next_sales

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
