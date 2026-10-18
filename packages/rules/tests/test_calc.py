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
