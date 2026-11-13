"""LOC-01: 입지 한 줄(역 등급 · 업무지구 · 가까운 정비사업)."""

from aucs_rules.appraisal_points import plan_zone, plan_zone_of_parcel
from aucs_rules.location import inside_zone, location, station_grade, zone_usable


def test_grade_by_straight_distance() -> None:
    assert station_grade(505) == "역세권"
    assert station_grade(500) == "초역세권"
    assert station_grade(2999) == "준역세권"
    assert station_grade(3001) is None and station_grade(None) is None


def test_location_line_and_direct_line() -> None:
    st = [
        {"name": "서울대입구역", "lines": ["2호선"], "straight_m": 505},
        {"name": "숭실대입구역", "lines": ["7호선"], "straight_m": 1240},  # 1km 밖 — 내 노선으로 안 침
    ]
    hubs = [
        {"name": "강남", "lines": ["2호선"], "straight_m": 9300},
        {"name": "여의도", "lines": ["5호선", "9호선"], "straight_m": 6500},
    ]
    zones = [
        {"key": "a", "name": "봉천4-1-3", "biz_type": "재개발", "stage": "사업시행인가", "straight_m": 530},
        {"key": "a", "name": "봉천4-1-3 구역", "biz_type": "재개발", "stage": "사업시행", "straight_m": 531},
        {"key": "b", "name": "끝난 곳", "biz_type": "재건축", "stage": "준공인가", "straight_m": 100},
    ]
    v = location(st, hubs, zones).value
    assert v["grade"] == "역세권"
    assert [h["direct"] for h in v["hubs"]] == [None, "2호선"]  # 가까운 순: 여의도 · 강남
    assert [z["name"] for z in v["redev"]] == ["봉천4-1-3"]  # 같은 지번은 하나 · 끝난 사업은 뺌
    assert v["line"] == "서울대입구역(2호선) 직선 505m 역세권 · 강남역까지 2호선 한 번에"  # 구역 밖은 한 줄에 없음
    ins = inside_zone({"name": "봉천4-1-3", "stage": "사업시행인가"}, None)
    v = location(st, hubs, zones, ins).value
    assert v["redev"] == [] and v["line"].endswith("정비구역 안(사업시행인가)")
    assert inside_zone(None, "district")["label"] == "재정비촉진지구 안"
    assert inside_zone(None, None) is None


def test_empty_and_zone_usable() -> None:
    v = location([], [], []).value
    assert v == {"grade": None, "hubs": [], "inside": None, "redev": [], "line": None}
    assert not zone_usable("조합해산", "재개발") and not zone_usable("착공", "지역주택조합")
    assert zone_usable("착공", "재건축")


def test_plan_zone_reads_land_use_list() -> None:
    assert plan_zone("대공방어협조구역<군사기지법>, 정비구역<도시 및 주거환경정비법>, 과밀억제권역") == "zone"
    assert plan_zone("정비구역(2025-10-16)<도시 및 주거환경정비법> 과밀억제권역") == "zone"
    assert plan_zone("(거여새마을 재정비촉진구역)") == "zone"
    assert plan_zone("재정비촉진지구(천호성내재정비촉진지구)<도시재정비 촉진을 위한 특별법>") == "district"
    assert plan_zone("정비예정구역(주택재개발)") == "planned" and plan_zone("정비구역(입안)") == "planned"
    # 조합이 없는 주거환경개선 · 존치구역 · 설명 글은 구역 안으로 보지 않음
    assert plan_zone("정비구역(주거환경개선사업)<도시 및 주거환경정비법>") is None
    assert plan_zone("재정비촉진지구기타(천호성내존치관리구역)") is None
    assert plan_zone("건축허가·착공제한지역(정비계획의 결정 및 정비구역의 지정·고시가 있는 경우)") is None


def test_plan_zone_of_parcel_skips_adjacent() -> None:
    uses = [{"name": "도시지역", "incl": "포함"}, {"name": "정비구역", "incl": "포함"}]
    assert plan_zone_of_parcel(uses) == "zone"
    assert plan_zone_of_parcel([{"name": "정비구역", "incl": "접함"}]) is None
    assert plan_zone_of_parcel([{"name": "재정비촉진지구", "incl": "저촉"}]) == "district"
    assert plan_zone_of_parcel(None) is None
