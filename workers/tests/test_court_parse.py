import json
from datetime import date
from pathlib import Path

from aucs_workers.collectors.parse import parse_item, parse_result, split_sigungu
from aucs_workers.extract.mask import mask_names

FIX = Path(__file__).parent / "fixtures"


def rows(name: str) -> list[dict]:
    return json.loads((FIX / name).read_text(encoding="utf-8"))["data"]["dlt_srchResult"]


def test_item_55580() -> None:
    r = next(x for x in rows("court_items_page.json") if x["srnSaNo"] == "2025타경55580")
    p = parse_item(r)
    it = p["item"]
    assert it["item_id"] == "B000250-2025타경55580-1"
    assert it["min_price_krw"] == 710_500_000  # 공고 최저가 (minmaePrice 는 직전값)
    assert it["appraisal_krw"] == 1_015_000_000
    assert (it["sido"], it["sigungu"], it["gu"]) == ("경기도", "용인시", "수지구")
    assert it["building_area_m2"] == 167.576
    assert abs(it["lat"] - 37.3212) < 0.001 and abs(it["lon"] - 127.0636) < 0.001
    assert p["round"]["round_id"] == "B000250-2025타경55580-1-20261020"


def test_items_all_parse() -> None:
    for r in rows("court_items_page.json"):
        p = parse_item(r)
        assert p["case"]["case_id"].startswith(r["boCd"])


def test_results_sold_and_failed() -> None:
    got = [parse_result(r) for r in rows("court_results_page.json")]
    sold = [g for g in got if g and g["result"] == "sold"]
    failed = [g for g in got if g and g["result"] == "failed"]
    assert len(sold) == 3 and len(failed) == 2
    assert all(g["winning_bid_krw"] and g["sale_rate"] for g in sold)
    assert all(g["winning_bid_krw"] is None for g in failed)
    assert all(isinstance(g["sale_date"], date) for g in sold)


def test_mask_and_split() -> None:
    assert mask_names("임차인 홍길동 배당요구") == "임차인 홍○○ 배당요구"
    assert split_sigungu("강남구") == ("강남구", None)
