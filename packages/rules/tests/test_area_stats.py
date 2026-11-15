from aucs_rules.area_stats import area_stats, kind_of

STATS = {
    "officetel_yield": {"경기": {"period": "2026년 9월", "value": 5.354, "unit": "%"}},
    "shop_yield": {
        "서울": {"period": "2026년 3분기", "value": 0.61, "unit": "%"},
        "서울>도심>광화문": {"period": "2026년 3분기", "value": 0.33, "unit": "%"},
    },  # fmt: skip
    "conv_apt": {
        "경기": {"period": "2026년 9월", "value": 5.9, "unit": "%"},
        "경기>수원시": {"period": "2026년 9월", "value": 5.5, "unit": "%"},
        "경남>수원시": {"period": "2026년 9월", "value": 9.9, "unit": "%"},
    },  # fmt: skip
}


def test_kind_of() -> None:
    assert kind_of("오피스텔", None) == "officetel"
    assert kind_of("상가,오피스텔,근린시설", "○○오피스텔 301호") == "officetel"
    assert kind_of("상가,오피스텔,근린시설", "○○프라자 101호") == "shop"
    assert kind_of("연립주택,다세대,빌라", None) == "row"
    assert kind_of("임야", None) is None


def test_area_stats() -> None:
    a = area_stats("아파트", None, "경기도", "수원시 영통구", STATS)
    assert a and a["items"] == [{"label": "전월세전환율", "value": 5.5, "unit": "%", "region": "수원시", "period": "2026년 9월"}]  # fmt: skip
    s = area_stats("근린시설", None, "서울특별시", "종로구", STATS)
    assert s and s["items"][0]["region"] == "서울" and s["items"][0]["per"] == "분기"
    o = area_stats("오피스텔", None, "경기도", "성남시 분당구", STATS)
    assert o and o["items"][0]["value"] == 5.35
    assert area_stats("아파트", None, "부산광역시", "해운대구", STATS) is None
    assert area_stats("아파트", None, "경기도", "수원시", None) is None
