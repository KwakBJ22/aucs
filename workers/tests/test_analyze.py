from datetime import date

from aucs_rules.risk import signals, top_signal
from aucs_workers.jobs.analyze import build_facts, doc_tenants


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


def test_doc_tenants_from_deliveries():
    """현황조사서에 임차인이 없을 때 문건 · 송달의 임차인 · 임차권자(11/24 서울동부 2024타경57221)."""
    ev = [
        {
            "text": "주택임차권자 이OO 최고서 발송",
            "category": "이해관계인 최고",
            "event_date": None,
            "after_deadline": False,
        },
        {
            "text": "주택임차권자 이OO 임차인통지서 발송",
            "category": "임차인 통지",
            "event_date": None,
            "after_deadline": False,
        },
        {
            "text": "채무자겸소유자 양OO 개시결정정본 발송",
            "category": "경매 개시",
            "event_date": None,
            "after_deadline": False,
        },
    ]
    assert doc_tenants(ev) == {"n": 1, "lease_only": True}
    ev.append(
        {
            "text": "임차인 김OO 권리신고및배당요구신청서 제출",
            "category": "권리신고·배당요구",
            "event_date": None,
            "after_deadline": False,
        }
    )
    assert doc_tenants(ev) == {"n": 2, "lease_only": False}
    ev.append({"text": "주택임차권자 이OO(OOOO) 매각기일 및 매각결정기일통지서 발송", "category": "매각기일 통지",
               "event_date": None, "after_deadline": False})  # fmt: skip
    assert doc_tenants(ev)["n"] == 2
    assert build_facts({}, ev, [], True)["doc_tenants"]["n"] == 2
    assert "doc_tenants" not in build_facts({}, ev, [{"move_in_date": None}], True)


def test_rehab_resumed():
    from datetime import date as _d

    from aucs_workers.jobs.analyze import rehab_resumed

    ev = [
        {"event_date": _d(2026, 3, 3), "category": "회생·파산"},
        {"event_date": _d(2026, 7, 28), "category": "경매 속행 신청"},
    ]
    assert rehab_resumed(ev)
    assert not rehab_resumed(ev[:1])


def test_status_report_tenants_have_unit():
    from aucs_workers.extract.case_docs import tenants_from_status_report

    sr = {
        "dlt_ordTsRlet": [{"objctSeq": 1, "dspslObjctSeq": 1}, {"objctSeq": 2, "dspslObjctSeq": 3}],
        "dlt_ordTsLserLtn": [
            {"intrpsNm": "이강준", "objctSeq": 1, "mvinDtlCtt": "2021.01.29."},
            {"intrpsNm": "김태영", "objctSeq": 2, "mvinDtlCtt": "2020.12.17."},
        ],
    }
    assert [t["item_no"] for t in tenants_from_status_report(sr)] == [1, 3]
