"""실제 등기부 글자인식 결과로 판정이 지금 시스템과 같은지 (정답 사례)."""

import json
from datetime import date
from pathlib import Path

import pytest
from aucs_rules.rights import analyze, local_tax_suspect
from aucs_workers.extract.registry import fix_date, ocr_to_rights

FIX = Path(__file__).parent / "fixtures"
CASES = sorted(FIX.glob("registry_*.json"))
TODAY = date(2026, 10, 17)


@pytest.mark.parametrize("path", CASES, ids=[p.stem for p in CASES])
def test_registry_case(path: Path) -> None:
    c = json.loads(path.read_text(encoding="utf-8"))
    rights = ocr_to_rights(c["rows"], TODAY)
    res = analyze(rights)
    base = res["base"].value
    exp = c["expect"]
    assert f"{base.section}-{base.rank_no}" == exp["base"]
    assert str(base.receipt_date) == exp["base_date"]
    got = {f"{r.section}-{r.rank_no}": j.value for r, j in res["rights"]}
    got = {k: v for k, v in got.items() if k in exp["judge"]}
    assert got == exp["judge"]
    if "lease_move_in" in exp:
        lease = next(r for r in rights if "임차권" in r.purpose)
        assert str(lease.move_in_date) == exp["lease_move_in"]
    if "local_tax" in exp:
        assert sorted(f"{r.section}-{r.rank_no}" for r in rights if local_tax_suspect(r)) == sorted(
            exp["local_tax"]
        )


def test_fix_date() -> None:
    assert fix_date("2021년18월9일", TODAY) == date(2021, 12, 9)
    assert fix_date("3023년1월5일", TODAY) == date(2023, 1, 5)
    assert fix_date("없음", TODAY) is None
