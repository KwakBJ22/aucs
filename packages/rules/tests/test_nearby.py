from datetime import date, datetime

from aucs_rules.nearby import land_trade_price, nearby_stores

TODAY = date(2026, 11, 16)


def test_nearby_stores():
    row = {"total": 337, "radius_m": 300, "by_large": {"교육": 36, "음식": 86, "소매": 58},
           "same_parcel": 3, "fetched_at": datetime(2026, 11, 16, 3, 0),
           "same_list": [{"floor": "1", "small": "카페"}, {"floor": "1", "small": "카페"},
                         {"floor": "2", "small": "미술학원"}]}  # fmt: skip
    s = nearby_stores(row)
    assert s["top"][0] == ["음식", 86] and s["ground"] == ["카페"] and s["fetched"] == "2026-11-16"
    assert nearby_stores({"total": 0}) is None and nearby_stores(None) is None


def test_land_trade_price():
    t = [{"deal_date": date(2026, 5, 1), "price_krw": 100_000_000, "land_area_m2": 100,
          "sub_type": "대|제2종일반주거지역", "contract_kind": None} for _ in range(5)]  # fmt: skip
    t += [{"deal_date": date(2026, 5, 1), "price_krw": 1, "land_area_m2": 100,
           "sub_type": "대|제2종일반주거지역", "contract_kind": "지분"}]  # fmt: skip
    r = land_trade_price("대지", ["제2종일반주거지역"], t, TODAY)
    assert r["per_m2_krw"] == 1_000_000 and r["n"] == 5 and r["basis"] == "zone"
    assert land_trade_price("대지", ["일반상업지역"], t, TODAY)["basis"] == "jimok"
    assert land_trade_price("전답", None, t, TODAY) is None
    assert land_trade_price("임야", None, t[:4], TODAY) is None
