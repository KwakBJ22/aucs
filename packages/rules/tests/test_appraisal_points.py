"""감정평가 요항 → 요점 · 사실 (11/4). 돈·권리에 걸리는 판단만 시험."""

from datetime import date

from aucs_rules.appraisal_points import appraisal_facts, parse_points
from aucs_rules.risk import signals
from aucs_rules.small_lease_region import region_class


def _e(cd: str, t: str) -> dict[str, str]:
    return {"aeeWevlMnpntItmCd": cd, "aeeWevlMnpntCtt": t, "aeeWevlMnpntDtlSeq": "1"}


def test_parse_points_cleans_and_drops_empty() -> None:
    pts = parse_points(
        [
            _e("00083003", "남서측근거리에 김포골드라인 &amp;apos;사우역&amp;apos; 소재함"),
            _e("00083014", "없  음.\n"),
            _e("00083018", "-"),
            _e("00083006", "별첨 건물 내부 구조도 참조."),
        ]
    )
    assert pts == [{"label": "교통", "text": "남서측근거리에 김포골드라인 '사우역' 소재함"}]


def test_facts_road_plan_station() -> None:
    pts = parse_points(
        [
            _e(
                "00083001",
                '서울 중랑구 "중랑초등학교" 북측 인근에 위치하고 각급 학교 등이 혼재하는 지역',
            ),
            _e("00083003", "인근에 노선버스 정류장 소재하고 근거리에 '사우역' 소재함"),
            _e("00083005", "남측으로 노폭 약 2~3m 내외의 포장도로와 접함"),
            _e(
                "00083011",
                "제1종일반주거지역, 과밀억제권역<수도권정비계획법>, 토지거래계약에관한허가구역(2025-08-26), 개발제한구역",
            ),
        ]
    )
    f = appraisal_facts(pts).value
    assert f["near_station"] == "사우역" and f["near_school"]
    assert f["narrow_road"] and f["road_max_m"] == 3
    assert f["overcrowded"] and f["land_permit_area"] and f["greenbelt"]


def test_no_station_from_jiyeok() -> None:
    pts = parse_points([_e("00083001", "단독주택 등이 혼재하는 지역으로 주위환경 보통")])
    assert "near_station" not in appraisal_facts(pts).value
    pts = parse_points([_e("00083003", "근거리에 지하철역(신촌역 및 홍대입구역)이 소재")])
    assert appraisal_facts(pts).value["near_station"] == "신촌역"


def test_blind_land_signals() -> None:
    f1 = appraisal_facts(parse_points([_e("00083004", "기호(10):맹지임.")])).value
    f2 = appraisal_facts(
        parse_points(
            [_e("00083004", "지적도상 맹지이나, 현황 본건 남측으로 노폭 약 2~3m 포장도로와 접함.")]
        )
    ).value
    assert f1["no_road"] == "yes" and f2["no_road"] == "check"
    s1 = {s.rule_id: s for s in signals({**f1, "usage_text": "대지"})}
    assert s1["risk.no_road"].level == "high" and s1["risk.no_road"].ftype == "T11"


def test_permit_area_is_info_not_danger() -> None:
    # 민사집행법 경매는 토지거래허가 예외(부동산거래신고법 시행령 제11조) — 위험이 아니라 알림
    s = {x.rule_id: x for x in signals({"land_permit_area": True})}
    assert s["risk.permit_exempt"].level == "info"


def test_narrow_road_only_for_land_or_house() -> None:
    assert not [
        s
        for s in signals({"narrow_road": True, "usage_text": "아파트"})
        if s.rule_id == "risk.narrow_road"
    ]
    assert [
        s
        for s in signals({"narrow_road": True, "usage_text": "단독주택"})
        if s.rule_id == "risk.narrow_road"
    ]


def test_incheon_small_lease_class() -> None:
    d = date(2025, 1, 1)
    assert region_class("인천광역시", "부평구", None, d, True).value == "overcrowded"
    assert region_class("인천광역시", "연수구", None, d, False).value == "metro"
    assert region_class("인천광역시", "강화군", None, d, None).value == "other"
    assert region_class("경기도", "남양주시", None, d, True).value == "overcrowded"


def test_old_appraisal_info() -> None:
    s = {
        x.rule_id: x
        for x in signals({"appraisal_date": date(2022, 3, 22), "as_of": date(2026, 11, 4)})
    }
    assert s["risk.old_appraisal"].level == "info" and "4년" in s["risk.old_appraisal"].title
    assert "risk.old_appraisal" not in {
        x.rule_id for x in signals({"appraisal_date": date(2026, 6, 1), "as_of": date(2026, 11, 4)})
    }
