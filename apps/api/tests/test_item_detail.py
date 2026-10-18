from datetime import date, datetime

from aucs_api.services.item_detail import build_detail, verdict, won
from test_items import TODAY, row


def full(**kw):
    kw.setdefault("computed_at", datetime(2026, 10, 17, 15, 30))
    return row(note_masked=None, sale_place="입찰법정", dept_name="경매5계", claim_deadline=date(2025, 12, 1),
               sale_rate={"p25": 78.0, "p50": 84.0, "p75": 90.0, "n": 40},
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


def test_build_calc_cases_and_cap():
    from aucs_api.services.item_detail import build_calc

    tables = {
        "regulated_areas": {"seoul_all": True, "gyeonggi": []},
        "loan_ltv": {"regulated": {"none": 40, "first_time": 70, "owner": 0}, "metro": {"none": 70, "first_time": 70, "owner": 0},
                     "other": {"none": 70, "first_time": 80, "owner": 60},
                     "caps_regulated": [[1_500_000_000, 600_000_000], [None, 200_000_000]], "cap_metro_krw": 600_000_000},
        "acquisition_tax": {"heavy": {"regulated": {"2": 8.0, "3": 12.0}, "other": {"3": 8.0}}, "edu_rate_of_basic": 10,
                            "edu_heavy": 0.4, "farm_over85": {"basic": 0.2, "8": 0.6, "12": 1.0}},
    }  # fmt: skip
    r = full(sido="서울특별시", address="서울 관악구", building_area_m2=84,
             market={"price_krw": 1_200_000_000}, new_item=False)  # fmt: skip
    d = build_calc(r, tables, bid_krw=None, homes=0, first_time=False, loan_krw=None)
    assert d["cls"] == "regulated" and len(d["cases"]) == 3
    assert d["selected"]["bid_krw"] == d["cases"][1]["bid_krw"]
    assert (
        d["cap_krw"] == 1_200_000_000 - d["selected"]["tax"]["tax_krw"] * 0 - 39_600_000 - 2_400_000
    )


def test_not_analyzed_says_pending():
    d = build_detail(full(computed_at=None), [], [], [], None, TODAY, [])
    assert d["analyzed"] is False and d["verdict"] == "오늘 오후 분석이 끝나면 보여요"
    assert d["questions"][2]["answer"] == "오늘 오후 분석이 끝나면 보여요"
