from aucs_rules.calc import acquisition_tax, area_class, bid_cases, cash_needed, loan_limit

REG = {"seoul_all": True, "gyeonggi": ["수원시 영통구", "구리시"]}
LTV = {"regulated": {"none": 40, "first_time": 70, "owner": 0},
       "metro": {"none": 70, "first_time": 70, "owner": 0},
       "other": {"none": 70, "first_time": 80, "owner": 60},
       "caps_regulated": [[1_500_000_000, 600_000_000], [2_500_000_000, 400_000_000], [None, 200_000_000]],
       "cap_metro_krw": 600_000_000}  # fmt: skip
TAX = {"basic": [], "heavy": {"regulated": {"2": 8.0, "3": 12.0}, "other": {"3": 8.0, "4": 12.0}},
       "edu_rate_of_basic": 10, "edu_heavy": 0.4, "farm_over85": {"basic": 0.2, "8": 0.6, "12": 1.0}}  # fmt: skip


def test_area_class() -> None:
    assert area_class("서울특별시", "서울 관악구 봉천동", REG) == "regulated"
    assert area_class("경기도", "경기도 수원시  영통구 매탄동", REG) == "regulated"
    assert area_class("경기도", "경기도 평택시 비전동", REG) == "metro"
    assert area_class("부산광역시", "부산 해운대구", REG) == "other"


def test_loan_limit() -> None:
    v = loan_limit(1_000_000_000, appraisal_krw=1_100_000_000, market_krw=1_200_000_000,
                   cls="regulated", homes=0, first_time=False, table=LTV).value  # fmt: skip
    assert v["loan_krw"] == 400_000_000
    first = loan_limit(1_000_000_000, appraisal_krw=None, market_krw=1_200_000_000,
                       cls="regulated", homes=0, first_time=True, table=LTV).value  # fmt: skip
    assert first["loan_krw"] == 600_000_000  # 70% = 7억 → 한도 6억
    own = loan_limit(500_000_000, appraisal_krw=None, market_krw=None,
                     cls="regulated", homes=1, first_time=False, table=LTV).value  # fmt: skip
    assert own["loan_krw"] == 0 and own["note"]


def test_acquisition_tax() -> None:
    assert (
        acquisition_tax(500_000_000, homes_after=1, cls="regulated", area_m2=84, table=TAX).value[
            "tax_krw"
        ]
        == 5_500_000
    )
    v = acquisition_tax(750_000_000, homes_after=1, cls="regulated", area_m2=84, table=TAX).value
    assert v["rate"] == 2.0
    h = acquisition_tax(500_000_000, homes_after=2, cls="regulated", area_m2=100, table=TAX).value
    assert h["heavy"] and h["total_pct"] == 9.0


def test_cash_and_cases() -> None:
    v = cash_needed(800_000_000, min_price_krw=700_000_000, appraisal_krw=1_000_000_000,
                    market_krw=1_100_000_000, area_m2=84, cls="regulated", homes=0, first_time=False,
                    usage="아파트", tables={"loan_ltv": LTV, "acquisition_tax": TAX}).value  # fmt: skip
    assert v["loan_krw"] == 320_000_000 and v["deposit_krw"] == 70_000_000
    assert v["cash_krw"] == 800_000_000 - 320_000_000 + v["tax"]["tax_krw"] + 1_600_000
    c = bid_cases(1_000_000_000, 800_000_000, 78.4, 84.0, 90.0)
    assert [x["bid_krw"] for x in c] == [800_000_000, 840_000_000, 900_000_000]


def test_temporary_two_and_selling_loan() -> None:
    h = acquisition_tax(
        500_000_000, homes_after=2, cls="regulated", area_m2=84, table=TAX, temporary_two=True
    ).value
    assert not h["heavy"] and h["tax_krw"] == 5_500_000
    v = loan_limit(500_000_000, appraisal_krw=None, market_krw=None, cls="regulated", homes=1,
                   first_time=False, table={**LTV, "regulated": {**LTV["regulated"], "owner_sell": 40}},
                   selling=True).value  # fmt: skip
    assert v["loan_krw"] == 200_000_000 and v["who"] == "owner_sell"


def test_first_home_relief() -> None:
    rel = {"price_max_krw": 1_200_000_000, "max_krw": 2_000_000}
    v = acquisition_tax(
        500_000_000, homes_after=1, cls="regulated", area_m2=84, table=TAX, relief=rel
    ).value
    assert v["relief_krw"] == 2_000_000 and v["tax_krw"] == 3_500_000
    big = acquisition_tax(
        1_300_000_000, homes_after=1, cls="regulated", area_m2=84, table=TAX, relief=rel
    ).value
    assert big["relief_krw"] == 0


def test_dsr_limits_loan() -> None:
    from aucs_rules.calc import dsr_limit

    d = {"limit_pct": 40, "base_rate_pct": 4.5, "stress_pp": {"regulated": 3.0}, "years": 30}
    v = dsr_limit(60_000_000, cls="regulated", table=d).value
    # 월 200만 원, 금리 7.5%, 30년 → 약 2억 8,600만
    assert 285_000_000 < v["loan_krw"] < 287_000_000
    assert (
        dsr_limit(60_000_000, other_monthly_krw=2_000_000, cls="regulated", table=d).value[
            "loan_krw"
        ]
        == 0
    )


MR = {
    "move_out": {"per_pyeong_krw": [50_000, 150_000], "min_krw": [1_500_000, 3_000_000],
                 "no_elevator_from_floor": 3, "no_elevator_add_pct": 30},
    "repair": {"bands": [[10, [0, 100_000]], [20, [100_000, 300_000]], [30, [300_000, 600_000]],
                         [999, [600_000, 1_000_000]]], "unknown": [100_000, 600_000]},
}  # fmt: skip


def test_move_out_cost():
    from aucs_rules.costs import move_out_cost

    small = move_out_cost(30.0, floor=2, elevators=0, table=MR)  # 9평 → 최소액
    assert (small["low_krw"], small["high_krw"]) == (1_500_000, 3_000_000) and not small["stairs"]
    big = move_out_cost(84.0, floor=5, elevators=0, table=MR)  # 25.4평, 승강기 없이 5층
    assert big["low_krw"] == 1_500_000 and big["stairs"] and big["high_krw"] == 4_950_000
    assert move_out_cost(None, floor=None, elevators=None, table=MR)["basis"] == "min"


def test_repair_cost():
    from aucs_rules.costs import repair_cost

    r = repair_cost(84.0, age_years=32, table=MR)
    assert (r["low_krw"], r["high_krw"]) == (15_250_000, 25_410_000)
    assert repair_cost(84.0, age_years=5, table=MR)["low_krw"] == 0
    assert repair_cost(84.0, age_years=None, table=MR)["basis"] == "unknown_age"
    assert repair_cost(None, age_years=10, table=MR)["mid_krw"] == 0


def test_rent_returns():
    from aucs_rules.costs import rent_returns

    r = rent_returns(1_000_000_000, cls="metro", loan_krw=400_000_000, rate_pct=4.5,
                     jeonse_krw=700_000_000, wolse_deposit_krw=200_000_000, wolse_rent_krw=2_400_000)  # fmt: skip
    assert r["loan_krw"] == 0 and r["no_loan_reason"] == "move_in_rule"
    assert r["jeonse"]["cash_krw"] == 300_000_000
    assert r["wolse"]["cash_krw"] == 800_000_000 and r["wolse"]["yield_pct"] == 3.6
    other = rent_returns(500_000_000, cls="other", loan_krw=200_000_000, rate_pct=5.0,
                         jeonse_krw=None, wolse_deposit_krw=50_000_000, wolse_rent_krw=1_500_000)  # fmt: skip
    assert (
        other["wolse"]["net_year_krw"] == 18_000_000 - 10_000_000
        and other["wolse"]["yield_pct"] == 3.2
    )
    assert rent_returns(1, cls="other", loan_krw=0, rate_pct=4.5, jeonse_krw=None,
                        wolse_deposit_krw=None, wolse_rent_krw=None) is None  # fmt: skip


def test_cash_at_min_by_homes() -> None:
    """11/9 찾기 「가진 현금」: 최저가에 낙찰받을 때 필요한 현금(대출·세금 감안), 가진 집 수별."""
    from aucs_rules.calc import cash_at_min

    v = cash_at_min(min_price_krw=300_000_000, appraisal_krw=400_000_000, market_krw=None,
                    area_m2=84.0, sido="경기도", address="경기도 평택시 비전동",
                    tables={"regulated_areas": REG, "loan_ltv": LTV, "acquisition_tax": TAX}, usage="아파트")  # fmt: skip
    assert set(v) == {"0", "1", "2"}
    assert v["0"] < 300_000_000 * 0.4  # 무주택은 70% 대출 → 30% + 세금쯤
    assert v["2"] > 300_000_000  # 집이 있으면(owner 0%) 대출 없이 전액 + 세금


def test_cash_at_min_unknown_marks_notax() -> None:
    """11/18: 용도 확인 안 됨이면 취득세가 빠진 금액이라는 표시(notax)를 붙임 — 주택이면 안 붙음."""
    from aucs_rules.calc import cash_at_min

    t = {"regulated_areas": REG, "loan_ltv": LTV, "acquisition_tax": TAX}
    kw = dict(min_price_krw=300_000_000, appraisal_krw=400_000_000, market_krw=None, area_m2=84.0,
              sido="경기도", address="경기도 평택시 비전동", tables=t)  # fmt: skip
    assert cash_at_min(**kw, usage="기타").get("notax") == 1
    assert "notax" not in cash_at_min(**kw, usage="아파트")


def test_non_house_tax():
    """상가 · 오피스텔 · 땅은 집 수와 상관없이 4.6%, 전답은 3.4%(지방세법 §11①7, 11/16)."""
    from aucs_rules.calc import tax_kind

    assert tax_kind("상가,오피스텔,근린시설 1층104호") == "other"
    assert tax_kind("오피스텔") == "other" and tax_kind("대지") == "other"
    assert tax_kind("전답") == "farm" and tax_kind("다세대 2층201호") == "house"
    assert tax_kind(None) == "unknown" and tax_kind("기타") == "unknown"
    assert tax_kind("기타 블리스타운2차 1동 2층205호") == "unknown"  # 설명만으로는 주택인지 모름
    assert tax_kind("기타 나동 공장 공장(지식산업센터)") == "other"
    assert tax_kind("기타 단독주택 단독주택") == "house"
    u = acquisition_tax(100_000_000, homes_after=1, cls="metro", area_m2=None, table=TAX, kind="unknown").value
    assert u["tax_krw"] == 0 and u["total_pct"] is None
    v = acquisition_tax(1_000_000_000, homes_after=3, cls="regulated", area_m2=44, table=TAX, kind="other").value
    assert v["total_pct"] == 4.6 and v["tax_krw"] == 46_000_000 and not v["heavy"]
    f = acquisition_tax(100_000_000, homes_after=1, cls="metro", area_m2=None, table=TAX, kind="farm").value
    assert f["total_pct"] == 3.4


def test_non_house_loan_not_from_house_table():
    """상가 · 땅에는 주택담보대출 비율을 쓰지 않음(11/17)."""
    v = cash_needed(500_000_000, min_price_krw=500_000_000, appraisal_krw=700_000_000, market_krw=None,
                    area_m2=44, cls="regulated", homes=0, first_time=False, usage="상가,오피스텔,근린시설",
                    tables={"loan_ltv": LTV, "acquisition_tax": TAX}).value  # fmt: skip
    assert v["loan_krw"] == 0 and v["loan"]["pct"] is None and v["tax"]["total_pct"] == 4.6


def test_usage_for_kind_order():
    from aucs_rules.calc import tax_kind, usage_for_kind

    # 주상복합 상가 호: 건물 주용도의 「공동주택」으로 주택이 되면 안 됨(더파인빌딩 805호, 11/17)
    u = usage_for_kind("상가,오피스텔,근린시설", "더파인빌딩 8층805호", None,
                       "업무시설 2종근린생활시설,공동주택(다세대-원룸형 도시형생활주택)")  # fmt: skip
    assert tax_kind(u) == "other"
    # 근생빌라 호: 그 호 전유 용도가 근린생활시설이면 주택 아님
    assert tax_kind(usage_for_kind("다세대", "빌라 3층301호", "제2종근린생활시설", "공동주택")) == "other"
    # 법원 「기타」 + 설명 없음 → 대장 주용도로
    assert tax_kind(usage_for_kind("기타", None, None, "공장")) == "other"
    assert tax_kind(usage_for_kind("기타", None, None, None)) == "unknown"
    assert tax_kind(usage_for_kind("아파트", "래미안 101동", None, None)) == "house"
    # 0.19.5: 그 호 대장은 주택인데 법원은 상가 · 오피스텔 → 주택 아닌 쪽(둘 다 주택이어야 주택 세율)
    assert tax_kind(usage_for_kind("상가,오피스텔,근린시설", "8층805호", "다세대주택", "공동주택")) == "other"
    assert tax_kind(usage_for_kind("아파트", "101동", "아파트", "공동주택")) == "house"
