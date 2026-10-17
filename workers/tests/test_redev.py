from aucs_workers.collectors.redev import split_lot, to_zone


def test_split_lot() -> None:
    assert split_lot("개포동 138") == ("개포동", 138, 0)
    assert split_lot("수송동146-12") == ("수송동", 146, 12)
    assert split_lot("신문로1가158") == ("신문로1가", 158, 0)
    assert split_lot("") == (None, None, 0)


def test_ended_zone_excluded() -> None:
    assert to_zone({"사업장명": "가", "진행단계": "조합해산"}) is None
    z = to_zone(
        {
            "사업장명": "개포1",
            "진행단계": "관리처분인가",
            "대표지번": "개포동 138",
            "자치구": "강남구",
        }
    )
    assert z and z["main_no"] == 138 and z["gu"] == "강남구"
