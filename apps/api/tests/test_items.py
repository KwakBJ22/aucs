from datetime import date

from aucs_api.services.items import card

TODAY = date(2026, 10, 17)


def row(**kw):
    base = {"item_id": "B000250-2025타경55580-1", "court_code": "B000250", "case_no": "2025타경55580",
            "sale_date": date(2026, 10, 20), "usage_name": "아파트", "sido": "경기도", "sigungu": "용인시",
            "gu": "수지구", "address": "", "building_desc": "성복힐스테이트3차 304동", "building_area_m2": 167.576,
            "appraisal_krw": 1_015_000_000, "min_price_krw": 710_500_000, "failed_count": 1, "is_share": False,
            "lat": 37.32, "lon": 127.06, "top": None, "signals": [], "data_status": {}}  # fmt: skip
    return {**base, **kw}


def test_card_numbers() -> None:
    c = card(row(), TODAY)
    assert c["d_day"] == 3 and c["min_rate"] == 70 and c["deposit_krw"] == 71_050_000
    assert (
        c["below_appraisal_krw"] == 304_500_000
        and c["court"] == "수원"
        and c["place"] == "용인시 수지구"
    )


def test_card_signal_skips_unknown() -> None:
    sig = [{"rule_id": "risk.tenants_unknown", "level": "info", "status": "모름", "title": "임차인 미확인"},
           {"rule_id": "risk.share", "level": "fatal", "status": "추정", "title": "지분 매각"}]  # fmt: skip
    c = card(row(signals=sig), TODAY)
    assert c["top_signal"]["rule_id"] == "risk.share" and c["unknown_count"] == 1


def test_parse_query():
    from aucs_api.services.items import parse_query

    assert parse_query("2025타경55580") == {"kind": "case", "case_no": "2025타경55580"}
    assert parse_query("25-55580") == {"kind": "case", "case_no": "2025타경55580"}
    assert parse_query(" 55580 ") == {"kind": "case_suffix", "suffix": "타경55580"}
    assert parse_query("성복 힐스테이트") == {"kind": "text", "text": "성복힐스테이트"}
    assert parse_query("") is None
