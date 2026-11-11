from datetime import date

from aucs_rules.building import dong_key, parse_jibun, summarize, unit_from_address

TODAY = date(2026, 10, 27)


def test_parse_jibun():
    assert parse_jibun("508-123") == ("0", "0508", "0123")
    assert parse_jibun("산12-3") == ("1", "0012", "0003")
    assert parse_jibun("화성태안3지구비-1블록^1289-3") == ("0", "1289", "0003")
    assert parse_jibun("화성태안3지구비-1블록") is None


def test_unit_from_address():
    cases = {
        "서울특별시 중랑구 중화동 99-4 제4층 제401호": {"dong": None, "floor": 4},
        "용인시 수지구 버들치마을성복힐스테이트3차 304동 2층203호": {"dong": "304", "floor": 2},
        "서울특별시 중랑구 중화동 42 중화동건영아파트 12층1208호": {"dong": None, "floor": 12},
        "서울 중구 신당동 217-91 5층가557호": {"dong": None, "floor": 5},
        "어딘가 가동 지하1층 101호": {"dong": "가", "floor": -1},
        "어딘가 제101동 제5층 제502호": {"dong": "101", "floor": 5},
        "화성시 동탄하나1길 61, 1409호 (능동)": {"dong": None, "floor": None},
        "고양시 일산서구 대화동 1474-2 주건축물제1동 3층301호": {"dong": "1", "floor": 3},
        "부천시 오정구 원종동 382-20 백합주택 에이동 지층1호": {"dong": "A", "floor": None},
    }
    for a, exp in cases.items():
        assert unit_from_address(a) == exp, a


def test_pick_dong_and_summary():
    titles = [
        {"dongNm": "303동", "totArea": "9000", "useAprDay": "20090315", "hhldCnt": "60"},
        {"dongNm": "304동", "totArea": "8000", "useAprDay": "20090315", "grndFlrCnt": "20",
         "hhldCnt": "80", "rideUseElvtCnt": "2", "indrAutoUtcnt": "100",
         "mainPurpsCdNm": "공동주택", "etcPurps": "아파트"},
    ]  # fmt: skip
    r = summarize(titles, [], "성복힐스테이트3차 304동 2층203호", "아파트", TODAY)
    assert r["households"] == 80 and r["age_years"] == 17 and r["elevators"] == 2
    assert r["parking"] == 100 and r["villa"] is None and r["buildings"] == 2


def test_neighborhood_villa():
    t = [{"totArea": "500", "useAprDay": "19900101", "mainPurpsCdNm": "공동주택"}]
    floors = [
        {"flrGbCdNm": "지상", "flrNo": "2", "mainPurpsCdNm": "제2종근린생활시설", "etcPurps": "사무소"},
        {"flrGbCdNm": "지상", "flrNo": "3", "mainPurpsCdNm": "공동주택", "etcPurps": "다세대주택"},
    ]  # fmt: skip
    assert summarize(t, floors, "중화동 1 2층201호", "다세대", TODAY)["villa"] == "confirmed"
    assert summarize(t, floors, "중화동 1 3층301호", "다세대", TODAY)["villa"] == "clear"
    mixed = [*floors, {"flrGbCdNm": "지상", "flrNo": "2", "mainPurpsCdNm": "공동주택"}]
    assert summarize(t, mixed, "중화동 1 2층201호", "다세대", TODAY)["villa"] == "mixed"
    # 상가로 나온 물건은 근생이어도 판단하지 않음
    assert summarize(t, floors, "중화동 1 2층201호", "근린시설", TODAY)["villa"] is None


def test_no_title():
    assert summarize([], [], "x", "다세대", TODAY) is None


def test_villa_signal_uses_register_first():
    from aucs_rules.risk import signals

    guess = {"usage_code": "21101", "usage_text": "다세대 주택"}
    ids = lambda f: {(s.rule_id, s.level) for s in signals(f)}  # noqa: E731
    assert ("risk.neighborhood_villa", "mid") in ids(guess)
    assert ("risk.neighborhood_villa", "high") in ids({**guess, "villa_by_register": "confirmed"})
    assert not any(
        r == "risk.neighborhood_villa" for r, _ in ids({**guess, "villa_by_register": "clear"})
    )


def test_same_unit() -> None:
    from aucs_rules.building import ho_from_address, same_unit

    a = "경기도 평택시 통복동 477 삼성아파트 제108동 제7층 제701호"
    assert ho_from_address(a) == "701"
    assert same_unit(a, "경기도 평택시 통복동 477 삼성 108동 7층701호")
    assert not same_unit(a, "경기도 평택시 통복동 477 삼성아파트 제108동 제7층 제702호")
    assert not same_unit(a, "경기도 평택시 통복동 477 삼성아파트 제109동 제7층 제701호")
    assert not same_unit(a, "경기도 평택시 통복동 477")  # 한쪽만 호수 → 모름
    assert same_unit(
        "경기도 양평군 강상면 송학리 12-3", "경기도 양평군 강상면 송학리 12-3 외 1필지"
    )


def test_dong_key():
    assert dong_key("주건축물제2동") == "2" and dong_key("제304동") == "304" and dong_key("105동") == "105"
    assert dong_key("에이") == "A" and dong_key("A동") == "A" and dong_key("") == ""
