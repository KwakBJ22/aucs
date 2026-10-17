"""실제 사건 30건: 배당요구종기·종기 뒤 신고·유치권·진행 판단이 지금 시스템과 같은지."""

import json
from pathlib import Path

import pytest
from aucs_rules.progress import judge_progress
from aucs_workers.extract.case_docs import case_basics, case_events

CASES = json.loads(
    (Path(__file__).parent / "fixtures" / "case_parity_30.json").read_text(encoding="utf-8")
)


@pytest.mark.parametrize("c", CASES, ids=[c["case"] for c in CASES])
def test_parity(c: dict) -> None:
    b = case_basics(c["case_info"])
    exp = c["expect"]
    assert (str(b["claim_deadline"]) if b["claim_deadline"] else None) == exp["claim_deadline"]
    ev = case_events(c["deliveries"], b["claim_deadline"])
    assert any(e["after_deadline"] for e in ev) == exp["late_claim"]
    assert any(e["category"] == "유치권 신고" for e in ev) == exp["lien"]
    prog = judge_progress([(e["event_date"], e["category"]) for e in ev if e["event_date"]])
    assert prog.value == exp["progress"]
