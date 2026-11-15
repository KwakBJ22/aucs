"""용도지역 · 도시계획시설(토지이용계획) · 중복경매 신호(11/15)."""

from aucs_rules.appraisal_points import land_plan_of_parcel
from aucs_rules.risk import signals

USES = [
    {"code": "UQA122", "name": "제2종일반주거지역", "incl": "포함"},
    {"code": "UQA001", "name": "도시지역", "incl": "포함"},
    {"code": "UQS117", "name": "소로2류(폭 8m~10m)", "incl": "저촉"},
    {"code": "UQS117", "name": "소로2류(폭 8m~10m)", "incl": "포함"},
    {"code": "UQS113", "name": "중로1류(폭 20m~25m)", "incl": "접함"},
    {"code": "UBA100", "name": "과밀억제권역", "incl": "포함"},
]


def test_zone_and_facility() -> None:
    p = land_plan_of_parcel(USES)
    assert p == {
        "zones": ["제2종일반주거지역"],
        "facilities": [{"name": "소로2류(폭 8m~10m)", "incl": "저촉"}],
    }
    assert land_plan_of_parcel([]) is None and land_plan_of_parcel(None) is None
    assert land_plan_of_parcel([{"code": "UBA100", "name": "과밀억제권역", "incl": "포함"}]) is None


def test_facility_signal_only_for_land_or_house() -> None:
    f = {"plan_facilities": ["소로2류(폭 8m~10m)"], "usage_text": "단독주택"}
    s = [x for x in signals(f) if x.rule_id == "risk.plan_facility"]
    assert s and s[0].level == "mid" and "소로2류" in s[0].title
    assert not [
        x for x in signals({**f, "usage_text": "아파트"}) if x.rule_id == "risk.plan_facility"
    ]


def test_duplicate_auction_signal() -> None:
    s = [x for x in signals({"duplicate_auction": True}) if x.rule_id == "risk.duplicate"]
    assert s and s[0].level == "info" and s[0].ftype == "T5"
