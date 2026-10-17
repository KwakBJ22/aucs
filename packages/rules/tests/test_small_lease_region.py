from datetime import date

from aucs_rules.result import Status
from aucs_rules.small_lease_region import region_class

D = date(2023, 3, 1)


def test_classes() -> None:
    assert region_class("서울특별시", "강남구", None, D).value == "seoul"
    assert region_class("경기도", "수원시", None, D).value == "overcrowded"
    assert region_class("경기도", "용인시", None, D).value == "overcrowded"
    assert region_class("경기도", "평택시", None, D).value == "metro"
    assert region_class("경기도", "양평군", None, D).value == "other"


def test_period_changes() -> None:
    # 김포: 2018 개정 땐 광역시급, 2021 개정부터 과밀억제 구분
    assert region_class("경기도", "김포시", None, date(2019, 1, 1)).value == "metro"
    assert region_class("경기도", "김포시", None, date(2022, 1, 1)).value == "overcrowded"
    assert region_class("경기도", "평택시", None, date(2019, 1, 1)).value == "other"
    assert region_class("경기도", "수원시", None, date(2017, 1, 1)).status == Status.UNKNOWN


def test_partial_cities() -> None:
    assert region_class("경기도", "남양주시", "호평동", D).value == "overcrowded"
    assert region_class("경기도", "남양주시", "별내동", D).value == "other"
    assert region_class("경기도", "남양주시", None, D).status == Status.NEEDS_CHECK
    assert region_class("경기도", "시흥시", "정왕동", D).status == Status.NEEDS_CHECK
