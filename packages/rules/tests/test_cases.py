"""실제 사건 정답 사례를 모두 통과해야 합니다 (tests/cases/*.json)."""

import json
from datetime import date
from pathlib import Path

import pytest
from aucs_rules.rights import Right, analyze
from aucs_rules.tenants import Tenant, family_tenant, opposing_power

CASES = sorted((Path(__file__).parent / "cases").glob("*.json"))


def _d(s: str | None) -> date | None:
    return date.fromisoformat(s) if s else None


@pytest.mark.parametrize("path", CASES, ids=[p.stem for p in CASES])
def test_case(path: Path) -> None:
    c = json.loads(path.read_text(encoding="utf-8"))
    rights = [
        Right(
            section=r["section"], rank_no=r["rank_no"], purpose=r["purpose"],
            receipt_date=_d(r.get("receipt_date")), receipt_no=r.get("receipt_no"),
            amount_krw=r.get("amount_krw"),
        )
        for r in c["rights"]
    ]  # fmt: skip
    res = analyze(rights)
    base = res["base"].value
    assert base.rank_no == c["expect"]["base_rank_no"]
    assert str(base.receipt_date) == c["expect"]["base_date"]
    got = {r.rank_no: j.value for r, j in res["rights"]}
    assert got == c["expect"]["judgments"]
    if "tenant" in c:
        t = Tenant(
            move_in_date=_d(c["tenant"].get("move_in_date")),
            relation_text=c["tenant"].get("relation_text", ""),
        )
        assert opposing_power(t, base.receipt_date).value is c["expect_tenant"]["opposing_power"]
        assert family_tenant(t).value is c["expect_tenant"]["family"]
