import json
from datetime import date
from pathlib import Path

import pytest
from aucs_workers.collectors.court_docs import archive_due, internal_no
from aucs_workers.extract.case_docs import case_basics, case_events

SAMPLE = json.loads(
    (Path(__file__).parent / "fixtures" / "case_docs_sample.json").read_text(encoding="utf-8")
)
T = date(2026, 10, 17)


def test_internal_no() -> None:
    assert internal_no("2023타경113350") == "20230130113350"
    with pytest.raises(ValueError):
        internal_no("2023가단1")


def test_archive_schedule() -> None:
    assert archive_due(date(2026, 10, 30), None, T) == (True, 13)  # 14일 안 처음
    assert archive_due(date(2026, 10, 30), date(2026, 10, 17), T)[0] is False
    assert archive_due(date(2026, 10, 22), date(2026, 10, 10), T)[0] is True  # 7일 안 한 번 더
    assert archive_due(date(2026, 10, 22), date(2026, 10, 16), T)[0] is False
    assert archive_due(date(2026, 10, 15), date(2026, 10, 10), T) == (True, 102)  # 기일 뒤 결과
    assert archive_due(date(2026, 11, 30), None, T)[0] is False


def test_case_docs_extract() -> None:
    b = case_basics(SAMPLE["case_info"])
    assert b["claim_deadline"] == date(2025, 8, 18) and b["dept_name"] == "경매7계"
    ev = case_events(SAMPLE["deliveries"], b["claim_deadline"])
    assert len(ev) == 28
    assert all(e["category"] and e["importance"] in ("high", "mid", "low") for e in ev)
    assert any(e["category"] == "경매 개시" for e in ev)


def test_status_report_tenants() -> None:
    from aucs_workers.extract.case_docs import (
        occupant_unknown,
        parse_dot_date,
        parse_krw,
        tenants_from_status_report,
    )

    assert parse_krw("150,000,000") == 150_000_000
    assert parse_krw("500만 원") == 5_000_000
    assert parse_krw("1억2,000만원") == 120_000_000
    assert parse_krw("미상") is None and parse_krw("없음") == 0
    assert parse_dot_date("2025.05.15.(전입세대확인서)") == date(2025, 5, 15)
    assert parse_dot_date("미전입") is None
    sr = {
        "dlt_ordTsLserLtn": [
            {
                "intrpsNm": "홍길동",
                "mvinDtlCtt": "2021.03.30.",
                "lesDposDts": "2억원",
                "rgstryCrtcpCfmtnCtt": "미상",
            }
        ],
        "dlt_ordTsRlet": [{"gdsPossCtt": "현장출장 방문 시 아무도 만나지 못하여(폐문부재)"}],
    }
    t = tenants_from_status_report(sr)[0]
    assert (
        t["name_masked"] == "홍○○" and t["deposit_krw"] == 200_000_000 and t["fixed_date"] is None
    )
    assert occupant_unknown(sr)
