from datetime import date

from aucs_rules.price import Trade, nearby_price


def test_nearby_price_same_dong():
    """같은 건물 거래가 적을 때 같은 동 비슷한 집(11/24 서울동부 2024타경57221 — 같은 건물 1건뿐)."""
    as_of = date(2026, 11, 24)
    mk = lambda ppm, lot, by=2020, area=26.0, d=date(2026, 6, 1): Trade(  # noqa: E731
        d, int(ppm * area), area, None, lot, by
    )
    trades = [mk(14_000_000 + i * 100_000, f"lot{i % 4}") for i in range(8)]
    trades += [
        mk(14_000_000, "old", by=1995),  # 지은 해 ±5년 밖
        mk(14_000_000, "big", area=40.0),  # 넓이 ±10% 밖
        mk(14_000_000, "stale", d=date(2025, 6, 1)),  # 1년 밖
        mk(60_000_000, "lot0"),  # 튀는 값
    ]
    v = nearby_price(trades, as_of=as_of, area_m2=25.85, build_year=2020).value
    assert v["n"] == 8 and v["lots"] == 4
    assert v["p25_krw"] <= v["p50_krw"] <= v["p75_krw"]
    assert abs(v["p50_krw"] - 14_350_000 * 25.85) < 1_000
    # 한 건물 거래만 있으면 「주변」이라 하지 않음
    one = [mk(14_000_000, "same") for _ in range(6)]
    assert nearby_price(one, as_of=as_of, area_m2=25.85, build_year=2020).value is None
