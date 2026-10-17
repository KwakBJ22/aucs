from datetime import date

from aucs_rules.risk import signals, top_signal
from aucs_workers.jobs.analyze import build_facts


def test_facts_to_signals() -> None:
    item = {
        "is_share": False,
        "usage_code": "21101",
        "usage_name": "근린생활시설",
        "building_desc": "다세대주택 3층",
        "note_masked": "대항력 포기 확약서 제출",
    }
    events = [
        {"event_date": date(2025, 5, 1), "category": "정지·취하 시도", "after_deadline": False},
        {"event_date": date(2025, 8, 1), "category": "권리신고·배당요구", "after_deadline": True},
    ]
    f = build_facts(item, events, [], has_status_report=False)
    ids = {s.rule_id for s in signals(f)}
    assert {
        "risk.neighborhood_villa",
        "risk.special_condition",
        "risk.stop",
        "risk.late_claim",
        "risk.tenants_unknown",
    } <= ids
    assert top_signal(signals(f)).level == "high"


def test_sigungu_from_address() -> None:
    from aucs_workers.jobs.analyze import sigungu_from_address

    assert sigungu_from_address("경기 용인시 수지구 성복동 760") == "용인시"
    assert sigungu_from_address("서울 강남구 역삼동 1") == "강남구"
    assert sigungu_from_address(None) is None
