from aucs_rules import RuleResult, Status


def test_result_keeps_status_and_rule_id() -> None:
    r = RuleResult(value=None, status=Status.UNKNOWN, rule_id="sample-0")
    assert r.status == "모름"
    assert r.evidence == []
