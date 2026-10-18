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


def test_worth_court_shift_and_schedule():
    d = build_detail(full(court_cell={"p50": 92.0, "diff": 8.0, "use_as_base": True, "n": 120},
                          local_peers=None, new_item=False),
                     [], [], [], None, TODAY, [])  # fmt: skip
    w = d["questions"][2]
    assert w["answer"] == "비슷한 물건은 감정가의 86~98%에 낙찰됐어요"
    assert w["body"]["notes"] == ["이 법원은 같은 조건에서 8%p 높게 팔려요"]
    assert d["questions"][3]["body"]["schedule_line"].startswith("낙찰되면 잔금")
    assert {x["key"] for x in d["schedule"]["rows"] if x["deadline"]} >= {"tax", "order_deadline"}


def test_worth_new_item():
    d = build_detail(full(new_item=True), [], [], [], None, TODAY, [])
    assert d["questions"][2]["answer"].startswith("처음 나온 물건")


def test_worth_with_market():
    m = {"price_krw": 1_200_000_000, "level": 1, "n": 5, "recent": []}
    d = build_detail(full(market=m, new_item=False), [], [], [], None, TODAY, [])
    # 감정가 1,015,000,000 × 78~90% ÷ 시세 1,200,000,000 → 66~76%
    assert d["questions"][2]["answer"] == "시세의 66~76%쯤에 낙찰될 것 같아요"
