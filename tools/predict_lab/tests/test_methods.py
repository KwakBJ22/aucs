"""예측 방식 시험: 미래 섞임 없음 · ② 30건 미만 제외 · 최저가 밑으로 안 감 · 확률 · 달 나누기."""

from datetime import date, timedelta

import pytest
from backtest import next_month
from methods import (
    Pred,
    brier,
    build_ratio_pools,
    calibration,
    cdf_from_quantiles,
    months_range,
    predict_ratio,
    predict_rule,
)


def _sold(d: date, rate: float, **kw) -> dict:
    app = 100_000_000
    row = dict(
        result="sold", category="아파트", sido="11", sgg="11140", court_code="B000210",
        case_no="x", item_no=1, sale_date=d, failed_count=1, appraisal_krw=app,
        min_price_krw=60_000_000, winning_bid_krw=int(app * rate / 100), sale_rate=rate,
        min_rate=60.0, area_m2=84.0, market_price_krw=None, market_ratio=None,
        signal_count=None, high_count=None, tenant_count=None,
    )  # fmt: skip
    row.update(kw)
    return row


def _target(d: date, **kw) -> dict:
    row = _sold(d, 70.0, result="?", winning_bid_krw=None, sale_rate=None)
    row.update(kw)
    return row


def test_방식1은_기준일_당일_거래를_쓰지_않는다():
    base = [_sold(date(2026, 9, 1) + timedelta(days=i), 70 + (i % 7)) for i in range(20)]
    target = _target(date(2026, 10, 1))
    without = predict_rule(base, target)
    same_day = _sold(date(2026, 10, 1), 150.0)  # 입찰일 당일 — 들어가면 안 됨
    after = _sold(date(2026, 10, 5), 180.0)  # 뒤 거래 — 들어가면 안 됨
    with_future = predict_rule(base + [same_day, after], target)
    assert without is not None and with_future is not None
    assert with_future.p50 == pytest.approx(without.p50)
    assert with_future.n == without.n


def test_방식1_pool_을_주면_같은_답():
    base = [_sold(date(2026, 9, 1) + timedelta(days=i), 60 + (i % 9)) for i in range(25)]
    target = _target(date(2026, 10, 1))
    pool = {"아파트": base}
    assert predict_rule(base, target).p50 == pytest.approx(
        predict_rule(base, target, pool=pool).p50
    )


def test_방식2는_비교_사례_30건_미만이면_뺀다():
    train = [_sold(date(2026, 9, 1), 70, market_price_krw=90_000_000) for _ in range(29)]
    target = _target(date(2026, 10, 1), market_price_krw=90_000_000, min_price_krw=1)
    assert predict_ratio(build_ratio_pools(train), target) is None
    train.append(_sold(date(2026, 9, 1), 70, market_price_krw=90_000_000))
    assert predict_ratio(build_ratio_pools(train), target) is not None


def test_방식2는_시세가_없으면_내지_않는다():
    train = [_sold(date(2026, 9, 1), 70, market_price_krw=90_000_000) for _ in range(40)]
    assert predict_ratio(build_ratio_pools(train), _target(date(2026, 10, 1))) is None


def test_방식2_최저가_밑으로_안_내려간다():
    train = [
        _sold(date(2026, 9, 1), 20, market_price_krw=100_000_000, winning_bid_krw=20_000_000)
        for _ in range(40)
    ]
    target = _target(date(2026, 10, 1), market_price_krw=100_000_000, min_price_krw=55_000_000)
    p = predict_ratio(build_ratio_pools(train), target)
    assert isinstance(p, Pred)
    assert p.p25 == p.p50 == p.p75 == 55_000_000


def test_확률_값은_0과_1_사이이고_커진다():
    qs = [60.0, 70.0, 80.0, 90.0, 100.0]
    xs = [40, 60, 70, 80, 90, 100, 110, 130]
    vals = [cdf_from_quantiles(x, qs) for x in xs]
    assert all(0.0 <= v <= 1.0 for v in vals)
    assert vals == sorted(vals)
    assert cdf_from_quantiles(80.0, qs) == pytest.approx(0.5)


def test_brier_와_칸():
    assert brier([1.0, 0.0], [1, 0]) == 0.0
    cal = calibration([(0.05, 0), (0.95, 1)], bins=10)
    assert cal[0]["건수"] == 1 and cal[-1]["건수"] == 1


def test_달_나누기():
    assert next_month(date(2026, 12, 1)) == date(2027, 1, 1)
    months = months_range(date(2026, 7, 1), date(2026, 11, 26))
    assert [m.month for m in months] == [7, 8, 9, 10, 11]


def test_머신러닝_분위수는_정렬되고_확률은_범위_안():
    pytest.importorskip("lightgbm")
    pytest.importorskip("sklearn")
    import ml

    train = []
    for i in range(120):
        d = date(2026, 8, 1) + timedelta(days=i % 90)
        rate = 60 + (i % 30)
        train.append(
            _sold(
                d,
                rate,
                result="sold" if i % 3 else "failed",
                winning_bid_krw=None if i % 3 == 0 else int(1e8 * rate / 100),
                sale_rate=rate if i % 3 else None,
            )
        )
    model = ml.fit(train, n_estimators=30)
    out = ml.predict(model, train[:10])
    for o in out:
        assert o["ratio_q"] == sorted(o["ratio_q"])
        assert 0.0 <= o["p_sold"] <= 1.0
