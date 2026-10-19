from aucs_rules.address_match import compare

ITEM = "경기도 용인시 수지구 성복동 760 버들치마을성복힐스테이트3차 304동 2층203호"
REG = "경기도 용인시 수지구 성복동 760 버들치마을성복힐스테이트3차 제304농 제2층 제203호"


def test_same_with_ocr_typo():
    assert compare(REG, ITEM)["result"] == "same"


def test_ho_differs():
    r = compare(REG.replace("제203호", "제303호"), ITEM)
    assert r["result"] == "unit_differs" and r["registry_unit"] == "304동 303호"
    assert r["item_unit"] == "304동 203호"


def test_other_lot_is_different():
    assert compare(REG.replace(" 760 ", " 761 "), ITEM)["result"] == "different"


def test_other_city_is_different():
    other = "서울특별시 관악구 봉천동 1712 관악푸르지오 제101동 제5층 제501호"
    assert compare(other, ITEM)["result"] == "different"


def test_missing_is_unknown():
    assert compare(None, ITEM)["result"] == "unknown"
    assert compare("경기도 용인시 수지구", ITEM)["result"] == "unknown"
