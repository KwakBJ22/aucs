from aucs_rules.appraisal_parts import appraisal_parts
from aucs_rules.result import Status


def test_land_and_building_with_extras_deduped() -> None:
    # 단독주택: 토지 · 건물 목록이 따로, 제시외는 목록마다 같은 줄이 되풀이돼 옴(실제 응답 모양)
    objs = [
        {"auctnLstDvsCd": "01", "aeeEvlAmt": 909440000},
        {"auctnLstDvsCd": "02", "aeeEvlAmt": 9924770},
    ]
    row = {"dspslObjctSeq": 2, "sugtBsdsBldSeq": 1, "evlAmt": 274000, "bldArDts": "2㎡",
           "etcUsgCtt": "화장실", "bldStrcDts": "시멘트벽돌조"}  # fmt: skip
    r = appraisal_parts(objs, [[row], [dict(row)]], [[], []])
    v = r.value
    assert r.status == Status.CONFIRMED
    assert v["kind"] == "land_and_building"
    assert v["land_krw"] == 909440000 and v["building_krw"] == 9924770
    assert v["building_pct"] == 1.1
    assert len(v["extras"]) == 1 and v["extras_krw"] == 274000 and v["extras"][0]["area_m2"] == 2
    assert v["land_right_m2"] is None


def test_unit_with_land_right_and_building_only() -> None:
    lr = [[{"landArDts": "1008㎡", "rgltRateDnmnVal": "1008", "rgltRateNmrtVal": "43.25"}]]
    v = appraisal_parts([{"auctnLstDvsCd": "03", "aeeEvlAmt": 1720000000}], [[]], lr).value
    assert v["kind"] == "unit" and v["unit_krw"] == 1720000000 and v["building_pct"] is None
    assert v["land_right_m2"] == 43.25 and v["land_total_m2"] == 1008
    assert (
        appraisal_parts([{"auctnLstDvsCd": "02", "aeeEvlAmt": 5}]).value["kind"] == "building_only"
    )
    assert appraisal_parts(None).status == Status.UNKNOWN
