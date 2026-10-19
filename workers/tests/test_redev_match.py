from aucs_workers.jobs.redev_match import dong_of, pick, zone_key


def test_zone_key():
    assert zone_key("뉴서울아파트, 개나리,열망연립 재건축정비사업") == "뉴서울"
    assert zone_key("광장극동아파트 재건축사업 (신속통합기획)") == "광장극동"
    assert zone_key("서울아파트 재건축정비사업") is None  # 너무 짧음 → 오인 방지


def test_dong_of():
    assert dong_of("서울특별시 관악구 신림동 739 뉴서울아파트") == "신림동"
    assert dong_of("서울특별시 영등포구 양평동1가 271 x") == "양평동1가"


def test_pick():
    zones = [
        {
            "name": "신림2재정비촉진구역",
            "biz_type": "재개발(주택정비형)",
            "stage": "철거",
            "main_no": 324,
            "sub_no": 25,
        },
        {
            "name": "뉴서울아파트 재건축정비사업",
            "biz_type": "재건축",
            "stage": "조합설립인가",
            "main_no": 1,
            "sub_no": 0,
        },
        {
            "name": "옛단지아파트 재건축",
            "biz_type": "재건축",
            "stage": "준공인가",
            "main_no": 9,
            "sub_no": 0,
        },
    ]
    assert pick({"lot_no": "324-25"}, zones)["how"] == "지번"
    assert (
        pick({"lot_no": "739", "building_desc": "뉴서울아파트 가동 4층"}, zones)["how"]
        == "단지 이름"
    )
    assert pick({"lot_no": "9", "building_desc": "옛단지아파트"}, zones) is None  # 끝난 사업
    assert pick({"lot_no": "10", "building_desc": "다른빌"}, zones) is None
    gu = [
        {
            "name": "역삼동(758,은하수,760)",
            "biz_type": "아파트지구재건축",
            "stage": "",
            "main_no": 758,
            "sub_no": 0,
            "dong_name": "역삼동",
        }
    ]
    assert pick({"lot_no": "681-26", "building_desc": "역삼동하나빌 6층"}, gu) is None
