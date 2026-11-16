from aucs_workers.collectors.redev_gg import to_zone


def test_to_zone() -> None:
    z = to_zone(
        {
            "SIGUN_NM": "고양시",
            "IMPRV_ZONE_NM": "행신Ⅰ-1구역",
            "BIZ_TYPE_NM": "재개발",
            "BIZ_STEP_NM": "추진위원회",
            "LOCPLC_ADDR": "경기도 고양시 덕양구 행신동 222번지 일원",
            "EXISTNG_HOUSNG_HSHLD_CNT": 662,
            "BIZ_IMPLMTN_HSHLD_CNT_TOTSUM": None,
            "ASOCNTMB_LOTOUT_HSHLD_CNT": "423",
            "GENRL_LOTOUT_HSHLD_CNT": "160",
            "RENT_HSHLD_CNT": 80,
            "IMPRV_ZONE_APPONT_FIRST_DE": "20221227",
            "PROPLSN_COMMISN_APRV_DE": "20230406",
            "ASSOCTN_FOUND_CONFMTN_DE": None,
        }
    )
    assert z and (z["gu"], z["dong_name"], z["main_no"], z["sub_no"]) == (
        "고양시",
        "행신동",
        222,
        0,
    )
    assert '"designated": "2022-12-27"' in z["detail"] and '"union"' not in z["detail"]
    assert (
        '"old": 662' in z["detail"] and '"sale": 583' in z["detail"] and '"new"' not in z["detail"]
    )
    assert to_zone({"SIGUN_NM": "안양시", "IMPRV_ZONE_NM": "가", "BIZ_STEP_NM": "준공"}) is None
    n = to_zone(
        {
            "SIGUN_NM": "광명시",
            "IMPRV_ZONE_NM": "나",
            "BIZ_STEP_NM": "예정구역",
            "LOCPLC_ADDR": "경기도 광명시 nan",
        }
    )
    assert n and n["main_no"] is None and n["detail"] is None
