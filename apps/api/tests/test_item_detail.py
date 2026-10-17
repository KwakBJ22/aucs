from datetime import date

from aucs_api.services.item_detail import build_detail, verdict, won
from test_items import TODAY, row


def full(**kw):
    return row(note_masked=None, sale_place="입찰법정", dept_name="경매5계", claim_deadline=date(2025, 12, 1),
               sale_rate={"p25": 78.0, "p50": 84.0, "p75": 90.0, "n": 40}, computed_at=None,
               case_id="B000250-2025타경55580", **kw)  # fmt: skip


def test_detail_five_questions():
    d = build_detail(full(), [{"sale_date": date(2026, 9, 1), "min_price_krw": 1_015_000_000, "result": "failed"}],
                     [], [], {"pct": 30, "verified": False}, TODAY)  # fmt: skip
    assert [q["key"] for q in d["questions"]] == ["buy", "hold", "worth", "cost", "check"]
    assert d["next_round"] == {"min_price_krw": 497_350_000, "reduction_pct": 30, "verified": False}
    assert d["questions"][2]["body"]["range_krw"] == [791_700_000, 913_500_000]
    assert d["rounds"][0]["result"] == "유찰" and d["tags"][0] == {"label": "현황조사", "ok": False}


def test_verdict_order():
    fatal = {"level": "fatal", "status": "추정", "title": "지분 매각"}
    unk = {"level": "info", "status": "모름", "title": "임차인 미확인"}
    assert verdict([unk, fatal]).startswith("지분 매각")
    assert verdict([unk]) == "큰 문제 신호는 없어요. 확인할 것 1가지만 보면 돼요"
    assert verdict([]) == "큰 문제 신호는 없어요"


def test_won():
    assert won(497_350_000) == "4억 9,735만" and won(71_050_000) == "7,105만"
