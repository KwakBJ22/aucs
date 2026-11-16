import json
from datetime import date

from aucs_workers.collectors.redev_seoul import as_of, to_zone


def test_to_zone() -> None:
    z = to_zone(
        {
            "DISTRICT": "용산구",
            "ZONE_NM": "효창공원앞역세권",
            "JIBUN_ADDR": "효창동 5-307",
            "BIZ_TYPE": "도시정비형 재개발",
            "BIZ_STAGE": "추진위",
            "EXISTING_HOUSEHOLDS": "1625",
            "ZONE_DESIGNATION_INIT_YMD": "2026-04-16",
            "PROMOTION_COMMITTEE_YMD": "2026-04-03",
            "ASSOCIATION_ESTABLISHMENT_YMD": "",
            "TOT_BUILT_HOUSEHOLDS": "2993",
            "SALE_BUILT_HOUSEHOLDS": "1800",
            "RENT_BUILT_HOUSEHOLDS": "0",
        }
    )
    assert z and (z["dong_name"], z["main_no"], z["sub_no"]) == ("효창동", 5, 307)
    assert '"committee": "2026-04-03"' in z["detail"] and '"union"' not in z["detail"]
    assert '"old": 1625' in z["detail"] and '"rent"' not in z["detail"]
    assert to_zone({"DISTRICT": "", "ZONE_NM": "가"}) is None


def test_as_of_is_quarter_end() -> None:
    def z(day: str, key: str = "plan") -> dict[str, str | None]:
        return {"detail": json.dumps({"dates": {key: day}})}

    zones = [
        z("2026-05-28"),
        z("2026-06-25"),
        z("2026-04-02"),
        z("2026-10-31", "move_end"),
        {"detail": None},
    ]
    assert as_of(zones, date(2026, 11, 16)) == date(2026, 6, 30)
    # 기준일 뒤에 한 건만 더 적힌 분기에는 안 끌려감
    assert as_of([*zones, z("2026-07-03")], date(2026, 11, 16)) == date(2026, 6, 30)
    assert as_of([{"detail": None}], date(2026, 11, 16)) == date(2026, 11, 16)
