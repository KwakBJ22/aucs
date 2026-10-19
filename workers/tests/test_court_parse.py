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


def test_region_from_messy_court_fields():
    from aucs_workers.collectors.parse import region_from

    assert region_from("서울", "구로구", "서울 구로구 경인로 390") == ("서울특별시", "구로구", None)
    assert region_from("남양주시", "천마산로", "남양주시 천마산로 25 104동") == (
        "경기도",
        "남양주시",
        None,
    )
    assert region_from("용인시", "처인구", "용인시 처인구 경안천로 40-1") == (
        "경기도",
        "용인시",
        "처인구",
    )
    assert region_from("경기도", "용인시 수지구", "경기도 용인시 수지구 동천동") == (
        "경기도",
        "용인시",
        "수지구",
    )
    assert region_from("평택시", "지산1로", "") == ("경기도", "평택시", None)


def test_region_keeps_good_court_fields_for_vehicles():
    from aucs_workers.collectors.parse import region_from

    # 자동차: 주소는 사용본거지라 법원 칸(강남구)을 그대로
    assert region_from("서울특별시", "강남구", "서울특별시 서초구 신흥말길 1-593") == (
        "서울특별시",
        "강남구",
        None,
    )


def test_area_sum_allows_space_and_newline():
    from aucs_workers.collectors.parse import area_sum

    assert abs(area_sum("철근콘크리트구조 147.8405 ㎡") - 147.84) < 0.01
    assert abs(area_sum("철근콘크리트구조\n84.9743 ㎡") - 84.974) < 0.01
    assert area_sum("1층 50.5㎡, 2층 1,050 ㎡") == 1100.5
    assert area_sum("철근콘크리트구조") is None


def test_building_area_falls_back_to_area_list_for_buildings_only():
    from aucs_workers.collectors.parse import building_area

    assert (
        building_area(
            {"pjbBuldList": "", "areaList": "철근콘크리트구조 30.69㎡", "convAddr": "[집합건물 ]"}
        )
        == 30.69
    )
    assert (
        building_area({"pjbBuldList": "", "areaList": "36.7㎡", "convAddr": "[토지 대 36.7㎡]"})
        is None
    )
