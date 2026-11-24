from aucs_rules.risk import signals
from aucs_rules.spec_facts import spec_facts


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
    f = spec_facts({"keep": "을구 1번 전세권, 을구 2번 주택임차권등기(다만 주택도시보증공사의 말소동의 확약서가 제출됨)"})
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
