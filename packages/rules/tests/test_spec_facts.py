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
