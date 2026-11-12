from datetime import date

from aucs_rules.land_value import HouseTrade, building_cost, land_value

T = {"building_per_m2": 1_000_000, "life_years": 50, "min_residual": 0.2, "months": 24, "min_n": 5}
D = date(2026, 11, 12)


def test_building_cost_age_and_floor():
    assert building_cost(100, 2026, D, T) == 100_000_000  # 새 건물
    assert building_cost(100, 2001, D, T) == 50_000_000  # 25년 → 절반
    assert building_cost(100, 1950, D, T) == 20_000_000  # 바닥 20%
    assert building_cost(100, None, D, T) == 20_000_000  # 모르면 바닥


def test_range_from_land_unit():
    # 대지 100㎡ · 연면적 100㎡ · 2001년(건물 5천만) 거래 다섯 건 → 땅값 ㎡당 500만·600만·700만·800만·900만
    trades = [HouseTrade(date(2026, 6, 1), 50_000_000 + u * 100, 100, 100, 2001)
              for u in (5_000_000, 6_000_000, 7_000_000, 8_000_000, 9_000_000)]  # fmt: skip
    r = land_value(land_m2=200, floor_area_m2=300, build_year=2001, trades=trades,
                   court_units=[], as_of=D, table=T).value  # fmt: skip
    assert r["land_unit"] == {"p25": 6_000_000, "p50": 7_000_000, "p75": 8_000_000}
    assert r["building_krw"] == 150_000_000
    assert (r["low_krw"], r["mid_krw"], r["high_krw"]) == (1_350_000_000, 1_550_000_000, 1_750_000_000)


def test_too_few_or_old_trades_unknown():
    old = [HouseTrade(date(2023, 1, 1), 900_000_000, 100, 100, 2001)] * 9
    assert land_value(land_m2=100, floor_area_m2=100, build_year=2001, trades=old,
                      court_units=[], as_of=D, table=T).value is None  # fmt: skip
    assert land_value(land_m2=None, floor_area_m2=100, build_year=2001, trades=old,
                      court_units=[], as_of=D, table=T).value is None  # fmt: skip
