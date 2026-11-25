from aucs_rules.risk import signals
from aucs_rules.spec_facts import note_facts, spec_facts


def test_none_values_mean_nothing():
    f = spec_facts({"keep": "해당사항없음", "superficies": "해당사항 없음", "remark": None})
    assert "prior_assumed_rights" not in f and "statutory_superficies" not in f


def test_spec_to_signals():
    f = spec_facts({
        "keep": "을구 순위번호 9번 주택임차권등기는 배당에서 보증금이 전액 변제되지 않으면 말소되지 않음",
        "superficies": None,
        "remark": "위반건축물 등재되어 있음. 대지권미등기",
    })  # fmt: skip
    ids = {s.rule_id for s in signals(f)}
    assert {"risk.prior_rights", "risk.illegal", "risk.land_right", "risk.lease_reg"} <= ids


def test_superficies_only_when_possible():
    assert spec_facts({"superficies": "법정지상권 성립 여지 있음"})["statutory_superficies"]
    assert "statutory_superficies" not in spec_facts({"superficies": "법정지상권 성립 여지 없음"})
    assert spec_facts(None) == {}


def test_subway_superficies_is_prior_right_not_lease():
    f = spec_facts({"keep": "1토지 을구 1번 구분지상권설정등기는 말소되지 않고 매수인에게 인수됨"})
    assert f["prior_assumed_rights"] and "lease_registration_with_power" not in f


def test_lease_reg_release_agreed():
    """보증기관 말소동의 확약서가 낸 임차권등기는 인수 신호가 아님(11/17)."""
    for keep in (
        "을구 순위 1번 주택임차권등기(다만 주택도시보증공사의 말소동의 확약서가 제출됨)",
        "매수인에게 대항할 수 있는 을구 3번 임차권등기(다만,서울보증보험주식회사의 말소동의 확약서가 제출됨)",
        "을구 순위번호 2번 주택임차권등기(다만 서울보증보험 주식회사로부터 주택임차권등기 말소 동의 확약서가 2026.03.02. 제출됨)",
    ):
        f = spec_facts({"keep": keep})
        ids = {s.rule_id for s in signals(f)}
        assert ids == {"risk.lease_reg_released"}, keep
    f = spec_facts(
        {
            "keep": "을구 1번 전세권, 을구 2번 주택임차권등기(다만 주택도시보증공사의 말소동의 확약서가 제출됨)"
        }
    )
    assert "risk.prior_rights" in {s.rule_id for s in signals(f)}


def test_guarantor_pledge_in_remark_only():
    """확약서가 비고에만 적힘(11/24 서울동부 2024타경57221) → 말소동의 신호, 「원문 확인」은 안 띄움."""
    remark = (
        "주택도시보증공사(양도전:임차인 이○○)로부터 2026.10.12.자에 '임차보증금에 대하여 우선변제권만 주장하고 "
        "대항력은 포기하며, 보증금 전액을 변제받지 못하더라도 임차권등기를 말소하는 데 동의한다'는 내용의 확약서가 제출됨."
    )
    f = spec_facts({"keep": None, "remark": remark, "item_remark": remark})
    assert f["lease_reg_released"]
    f["note"] = f.pop("spec_note")
    ids = {s.rule_id for s in signals(f)}
    assert ids == {"risk.lease_reg_released"}
    # 확약서 말고 다른 조건(일괄매각)이 같이 있으면 「원문 확인」은 그대로
    f["note"] += " 일괄매각"
    assert "risk.special_condition" in {s.rule_id for s in signals(f)}


def test_tenant_in_docs_only():
    """현황조사서엔 없는데 문건에 임차인이 있으면 확인 필요(11/24)."""
    ids = {s.rule_id for s in signals({"doc_tenants": {"n": 1, "lease_only": False}})}
    assert ids == {"risk.tenant_unlisted"}
    # 임차권자 하나뿐이고 보증기관 말소동의면 위 신호가 다 말함
    ids = {s.rule_id for s in signals({"doc_tenants": {"n": 1, "lease_only": True},
                                       "lease_reg_released": ["확약서"]})}  # fmt: skip
    assert ids == {"risk.lease_reg_released"}


# ── 비고 글(11/24 종류별 검증 — 법원 목록 비고 원문 그대로)


def test_note_farmland():
    f = note_facts(
        "1. 특별매각조건으로 농지취득자격증명 필요(미제출시 보증금 몰수) 2. 원상회복명령"
    )
    assert f.get("farmland_permit") is True
    assert not note_facts("농지취득자격증명 불요").get("farmland_permit")


def test_note_lien_unclear_counts():
    f = note_facts(
        "2.양계성이 2025.5.30. 유치권신고(공사대금:176,000,000원)를 하였으나 그 성립여부는 불분명함."
    )
    assert f.get("lien_reported") is True
    assert not note_facts("유치권 신고가 있었으나 철회됨").get("lien_reported")


def test_note_senior_tenant():
    f = note_facts(
        "임차인 남○○ 대항력있는 임차인으로 배당에서 보증금이 전액 변제되지 아니하면 잔액을 매수인이 인수함."
    )
    assert f.get("senior_tenant_assumed") is True


def test_note_guarantor_waiver_condition_is_released():
    f = note_facts(
        "임차인 및 임차보증금반환채권승계인 주택도시보증공사의 매수인에 대한 대항력 포기조건 매각"
    )
    assert f.get("lease_reg_released")
    assert not f.get("senior_tenant_assumed")


def test_note_waiver_not_when_spec_keeps_rights():
    f = note_facts("주택도시보증공사의 대항력 포기조건 매각", {"prior_assumed_rights": ["전세권"]})
    assert not f.get("lease_reg_released")


def test_note_superficies_and_resale():
    assert note_facts("법정지상권 성립여부는 불분명").get("statutory_superficies") is True
    assert not note_facts("법정지상권 성립 여지 없음").get("statutory_superficies")
    assert note_facts("재매각. 매수보증금은 최저매각가격의 20%임").get("resale") is True


def test_note_negations_after_rerun():
    # 11/24 재분석 뒤 실제 비고 글
    assert not note_facts(
        "현황 밭으로 조사되었으나 농지취득자격증명이 필요하지 않다는 시흥시 사실조회 회신있음."
    ).get("farmland_permit")
    assert not note_facts("2. 건물만 매각, 법정지상권 없음 3. 제시외 건물 포함").get(
        "statutory_superficies"
    )
    assert note_facts("관습법상법정지상권 성립여부 알 수 없음.").get("statutory_superficies")
    assert note_facts(
        "유치권 점유 없었으나, 현황재조사시 1층 공동출입문에 유치권행사중으로 무단출입을 금한다 경고표시"
    ).get("lien_reported")
    assert note_facts("허위의 유치권행사 현수막 게시임을 이유로 유치권배제 신청서가 접수 됨.").get(
        "lien_reported"
    )
    assert not note_facts("유치권점유신고서 제출하였으나 유치권점유 취하서 제출함").get(
        "lien_reported"
    )


def test_note_pledge_by_tenant_or_creditor():
    # 11/25 수원 2025타경58164 비고 원문
    f = note_facts(
        "신청채권자로부터 2026.6.1.자에 '임차보증금에 대하여 우선변제권만 주장하고 대항력은 포기하며, "
        "전액을 변제받지 못하더라도 임차권등기를 말소해 주겠다.'는 내용의 확약서가 제출됨"
    )
    assert f.get("lease_reg_released") and f.get("lease_reg_released_by") == "other"
    assert note_facts("특별매각조건(대항력포기조건) 있음 · 채권자의 매수인에 대한 대항력 포기조건 매각").get(
        "lease_reg_released"
    )
    g = note_facts("한국주택금융공사로부터 대항력은 포기하며 임차권등기를 말소해 주겠다는 확약서가 제출됨")
    assert g.get("lease_reg_released") and not g.get("lease_reg_released_by")
