from datetime import date, datetime

from aucs_api.services.item_detail import build_detail, verdict, won
from test_items import TODAY, row


def full(**kw):
    kw.setdefault("computed_at", datetime(2026, 10, 17, 15, 30))
    kw.setdefault("sale_rate", {"p25": 78.0, "p50": 84.0, "p75": 90.0, "n": 40})
    return row(note_masked=None, sale_place="입찰법정", dept_name="경매5계", claim_deadline=date(2025, 12, 1),
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
    d = build_detail(full(new_item=True, min_price_krw=1_015_000_000), [], [], [], None, TODAY, [])
    assert d["questions"][2]["answer"] == "처음 나온 물건이라 보통 감정가보다 비싸게 팔려요"


def test_worth_checks_from_100_sample():
    # 시세가 감정가보다 낮은 신건 → 「비싸게 팔려요」라고 하지 않음
    m = {"price_krw": 850_000_000, "level": 1, "n": 3, "recent": []}
    d = build_detail(
        full(new_item=True, min_price_krw=1_015_000_000, market=m), [], [], [], None, TODAY, []
    )
    assert (
        d["questions"][2]["answer"] == "처음 나온 물건이지만 시세(8억 5,000만)가 감정가보다 낮아요"
    )
    # 유찰 수가 0으로 와도 최저가가 70%면 신건으로 보지 않음
    d = build_detail(full(new_item=True), [], [], [], None, TODAY, [])
    assert not d["questions"][2]["answer"].startswith("처음 나온")
    # 감정가가 시세의 절반 아래 → 시세 비교 빼고 이유 한 줄 (이유 모르면 체크리스트에도)
    m2 = {"price_krw": 2_100_000_000, "level": 1, "n": 3, "recent": []}
    d2 = build_detail(full(market=m2, new_item=False), [], [], [], None, TODAY, [])
    w = d2["questions"][2]
    assert w["answer"].startswith("비슷한 물건은 감정가의")
    assert w["body"]["notes"] == [
        "감정가가 같은 단지 거래(21억)와 크게 달라요 · 다른 평형 거래일 수도 있어요"
    ]
    assert any(x["key"] == "appraisal_gap" for x in d2["questions"][4]["body"]["checklist"])
    # 지분 매각이면 그 이유로, 체크리스트에는 안 올림
    sh = [{"rule_id": "risk.share", "level": "fatal", "status": "추정", "title": "지분 매각"}]
    d3 = build_detail(
        full(market=m2, new_item=False, is_share=True, signals=sh), [], [], [], None, TODAY, []
    )
    assert d3["questions"][2]["body"]["notes"][0].startswith("지분만 파는 물건이라")
    assert not any(x["key"] == "appraisal_gap" for x in d3["questions"][4]["body"]["checklist"])
    # 신건인데 감정가가 시세의 1.6배 넘음 → 「비싸게 팔려요」 아님
    m3 = {"price_krw": 500_000_000, "level": 1, "n": 3, "recent": []}
    d4 = build_detail(
        full(market=m3, new_item=True, min_price_krw=1_015_000_000), [], [], [], None, TODAY, []
    )
    assert d4["questions"][2]["answer"].startswith(
        "처음 나온 물건이에요 · 감정가가 시세와 크게 달라"
    )
    # 법원 보정이 p50에도 들어감
    d = build_detail(full(court_cell={"p50": 92.0, "diff": 8.0, "use_as_base": True, "n": 120}, new_item=False),
                     [], [], [], None, TODAY, [])  # fmt: skip
    r = d["questions"][2]["body"]["rate"]
    assert r["p25"] <= r["p50"] <= r["p75"] and r["p50"] == 92.0
    # 맨 위 「확인할 것 N가지」와 체크리스트 수가 같음
    unk = [
        {
            "level": "info",
            "status": "모름",
            "title": "임차인 자료 미확인",
            "rule_id": "risk.tenants_unknown",
        }
    ]
    d = build_detail(full(signals=unk), [], [], [], None, TODAY, [])
    n = sum(1 for x in d["questions"][4]["body"]["checklist"] if x["state"] != "확인 완료")
    assert f"확인할 것 {n}가지" in d["verdict"] and d["questions"][4]["answer"].startswith(
        f"확인할 것 {n}가지"
    )


def test_worth_range_not_below_min():
    low = {"p25": 50.0, "p50": 55.0, "p75": 60.0, "n": 30}
    d = build_detail(full(sale_rate=low, new_item=False), [], [], [], None, TODAY, [])
    lo, hi = d["questions"][2]["body"]["range_krw"]
    assert lo >= 710_500_000 and hi >= lo
    assert d["questions"][2]["answer"].endswith("최저가 근처에서 낙찰될 것 같아요")


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


def test_checklist_states_and_flow():
    from aucs_api.services.checklist import build_checklist

    sig = [
        {
            "rule_id": "risk.special_condition",
            "title": "비고의 매각 조건 — 원문 확인",
            "status": "확인 필요",
        }
    ]
    cl = build_checklist(
        {"status_report": "extracted"}, {"status_report": datetime(2026, 10, 17, 16, 37)}, sig
    )
    assert cl[0]["state"] == "전문가 확인 필요" and cl[-1]["state"] == "확인 완료"
    done = next(x for x in cl if x["key"] == "status_report")
    assert done["evidence"] == {"doc": "현황조사서", "fetched_at": "2026-10-17 16:37"}
    d = build_detail(
        full(),
        [{"sale_date": date(2026, 9, 1), "min_price_krw": 1, "result": "failed"}],
        [],
        [],
        None,
        TODAY,
        [],
    )
    q = d["questions"][4]
    assert q["answer"].startswith("확인할 것")
    flow = {f["key"]: f for f in q["body"]["flow"]}
    assert (
        flow["first"]["date"] == "2026-09-01" and flow["first"]["done"] and flow["pay"]["estimated"]
    )
