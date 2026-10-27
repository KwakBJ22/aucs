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
                    tables={"loan_ltv": LTV, "acquisition_tax": TAX}).value  # fmt: skip
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
