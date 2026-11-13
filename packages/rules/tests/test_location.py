"""LOC-01: 입지 한 줄(역 등급 · 업무지구 · 가까운 정비사업)."""

from aucs_rules.location import location, station_grade, zone_usable


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
    assert v["line"] == "서울대입구역(2호선) 직선 505m 역세권 · 강남역까지 2호선 한 번에 · 1km 안 정비사업 1곳"


def test_empty_and_zone_usable() -> None:
    v = location([], [], []).value
    assert v == {"grade": None, "hubs": [], "redev": [], "line": None}
    assert not zone_usable("조합해산", "재개발") and not zone_usable("착공", "지역주택조합")
    assert zone_usable("착공", "재건축")
