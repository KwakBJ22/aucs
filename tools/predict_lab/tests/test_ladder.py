"""강사님 장부 방식 ④ 새 방식 · ⑤ 사다리: 회차 셈 · 넓히는 순서 · N 미만이면 다음 단 · 이상치는 비교 사례에서만 · 미래 섞임 없음."""

from datetime import date, timedelta

import pytest
from ladder import (
    FLOOR_N,
    LadderIndex,
    add_ladder_rounds,
    ladder_round,
    predict_ladder,
    predict_new,
    trim_iqr,
)

D0 = date(2026, 10, 15)


# ---------- 회차 셈 ----------
def test_저감_20퍼센트_법원_회차():
    assert [ladder_round(x, 20) for x in (100, 80, 64, 51.2, 41, 32.8)] == [0, 1, 2, 3, 4, 5]
    assert ladder_round(63.0, 20) == 2  # 사다리 값과 조금 달라도 가장 가까운 회차


def test_저감_30퍼센트_법원_회차():
    assert [ladder_round(x, 30) for x in (100, 70, 49, 34.3, 24)] == [0, 1, 2, 3, 4]


def test_못_세는_경우():
    assert ladder_round(57.0, 20) is None  # 64 · 51.2 사이 — 어느 쪽도 2%p 안이 아님
    assert ladder_round(75.0, 30) is None  # 70 과 100 사이도 아님(70 과 5%p)
    assert ladder_round(64.0, None) is None  # 저감률 모르는 법원
    assert ladder_round(None, 20) is None
    assert ladder_round(66.0, 20) == 2  # 정확히 2%p 어긋남은 센다
    assert ladder_round(66.1, 20) is None  # 2%p 를 넘으면 못 셈


def test_회차_셈_결과_통계():
    rows = [
        dict(court_code="B1", category="아파트", min_rate=64.0, eff_failed=2, price_round=2),
        dict(
            court_code="B1", category="아파트", min_rate=64.0, eff_failed=3, price_round=None
        ),  # 지금 회차와 다름
        dict(court_code="B1", category="빌라", min_rate=57.0, eff_failed=2, price_round=2),  # 못 셈
        dict(
            court_code="B9", category="빌라", min_rate=64.0, eff_failed=2, price_round=2
        ),  # 저감률 모르는 법원
    ]
    st = add_ladder_rounds(rows, {"B1": 20.0})
    assert [r["ladder_round"] for r in rows] == [2, 2, None, None]
    assert st["셈"] == 2 and st["못 셈"] == 2
    assert st["저감률 모르는 법원"] == 1 and st["사다리에서 2%p 넘게 벗어남"] == 1
    assert st["지금 쓰는 회차와 같은 비율"]["eff_failed"]["같음"] == 1
    assert st["지금 쓰는 회차와 같은 비율"]["price_round(우리 자료)"] == {
        "같음": 1,
        "비교한 줄": 1,
        "%": 100.0,
    }


# ---------- 사다리 · 새 방식 ----------
def _sold(
    d: date, rate: float, *, sgg="G1", court="B1", cat="아파트", rd=2, pct=20.0, **kw
) -> dict:
    row = dict(
        result="sold", sale_rate=rate, ladder_round=rd, ladder_pct=pct, category=cat, sgg=sgg, court_code=court,
        sale_date=d, appraisal_krw=100_000_000, min_price_krw=64_000_000, winning_bid_krw=int(1e6 * rate),
    )  # fmt: skip
    row.update(kw)
    return row


def _many(n: int, rate: float, **kw) -> list[dict]:
    return [_sold(D0 - timedelta(days=1 + i % 60), rate, **kw) for i in range(n)]


def _target(**kw) -> dict:
    return _sold(D0, 0.0, result="?", sale_rate=None, min_price_krw=1, **kw)


def test_사다리는_구_법원_용도군_전용도_순서로_넓힌다():
    # 구 G1 에 10건(70%) · 같은 법원 B1 다른 구 20건(75%) · 같은 용도군 다른 법원 30건(80%) · 다른 용도 40건(85%)
    rows = (
        _many(10, 70, sgg="G1", court="B1")
        + _many(20, 75, sgg="G2", court="B1")
        + _many(30, 80, sgg="G3", court="B2")
        + _many(40, 85, sgg="G4", court="B3", cat="빌라")
    )
    ix = LadderIndex(rows)
    t = _target()
    for n_min, scope, rate in (
        (10, "구", 70),
        (30, "법원", 75),
        (60, "용도군", None),
        (100, "전 용도", None),
    ):
        p = predict_ladder(ix, t, n_min, False)
        assert p is not None and p["scope"] == scope, (n_min, p)
        if rate:  # 구 10건은 모두 70%, 법원 30건(70% 10건 + 75% 20건)의 가운데는 75%
            assert p["mid"] == pytest.approx(100_000_000 * rate / 100)


def test_표본이_N건_미만이면_다음_단으로():
    rows = _many(9, 70, sgg="G1", court="B1") + _many(30, 80, sgg="G2", court="B1")
    ix = LadderIndex(rows)
    p = predict_ladder(ix, _target(), 10, False)
    assert p["scope"] == "법원"  # 구는 9건 < 10 → 법원 단(39건)
    assert p["n"] == 39


def test_끝까지_N이_안_차면_가장_넓은_단이_5건_이상일_때만_낸다():
    ix = LadderIndex(_many(FLOOR_N, 70))
    p = predict_ladder(ix, _target(), 50, False)
    assert p is not None and "N 미달" in p["scope"]
    assert predict_ladder(LadderIndex(_many(FLOOR_N - 1, 70)), _target(), 50, False) is None


def test_같은_저감률_회차_안에서만_넓힌다():
    rows = _many(40, 70, rd=1) + _many(40, 90, pct=30.0)  # 회차 · 저감률이 다른 것은 안 섞임
    assert predict_ladder(LadderIndex(rows), _target(), 10, False) is None
    assert predict_ladder(LadderIndex(rows + _many(12, 60)), _target(), 10, False)["n"] == 12


def test_새_방식은_법원_칸이_N건_이상이면_법원_칸_아니면_법원_없이_칸():
    rows = _many(12, 60, court="B1") + _many(30, 80, court="B2")
    ix = LadderIndex(rows)
    p = predict_new(ix, _target(), 10, False)
    assert p["scope"] == "법원 칸" and p["n"] == 12
    p = predict_new(ix, _target(), 30, False)  # 법원 칸 12건 < 30 → 법원 없이 그 칸(42건)
    assert p["scope"] == "칸" and p["n"] == 42
    assert (
        predict_new(LadderIndex(_many(FLOOR_N - 1, 60)), _target(), 10, False) is None
    )  # 칸이 너무 적음


def test_회차를_못_센_물건은_뺀다():
    ix = LadderIndex(_many(40, 70))
    t = _target(rd=None)
    assert predict_new(ix, t, 10, False) is None and predict_ladder(ix, t, 10, False) is None


def test_예측은_최저가_밑으로_안_간다():
    ix = LadderIndex(_many(40, 40))  # 낙찰가율 40% 인데
    t = _target()
    t["min_price_krw"] = 64_000_000
    for f in (predict_new, predict_ladder):
        p = f(ix, t, 10, False)
        assert p["lo"] == p["mid"] == p["hi"] == 64_000_000 and p["p10"] == 64_000_000


# ---------- 이상치는 비교 사례에서만 ----------
def test_이상치는_사분위_범위_1점5배_밖을_뺀다():
    xs = sorted([70.0] * 20 + [72.0] * 20 + [300.0])
    assert 300.0 not in trim_iqr(xs) and len(trim_iqr(xs)) == 40
    assert trim_iqr([1.0, 2.0, 300.0]) == [1.0, 2.0, 300.0]  # 4건 미만은 그대로


def test_이상치는_비교_사례에서만_빼고_맞힐_물건은_그대로():
    rows = _many(30, 70) + _many(6, 300)  # 비교 사례에 300% 이상치 6건
    ix = LadderIndex(rows)
    raw = predict_ladder(ix, _target(), 10, False)
    cut = predict_ladder(ix, _target(), 10, True)
    assert raw["n"] == 36 and cut["n"] == 30
    assert cut["p90"] == pytest.approx(100_000_000 * 0.70, rel=0.01)  # 뺀 쪽은 이상치 영향이 없음
    assert raw["p90"] > cut["p90"]
    # 맞힐 물건 자신의 낙찰가율이 이상치여도 그 물건은 맞히기에서 안 빠진다(예측은 만들어짐)
    t = _sold(D0, 300.0)
    assert predict_ladder(ix, t, 10, True) is not None


# ---------- 미래 섞임 없음 ----------
def test_입찰일_당일_뒤_365일_넘은_낙찰은_비교_사례가_아니다():
    old = [_sold(D0 - timedelta(days=366 + i), 70) for i in range(20)]
    same_day = [_sold(D0, 70) for _ in range(20)]
    after = [_sold(D0 + timedelta(days=1 + i), 70) for i in range(20)]
    ix = LadderIndex(old + same_day + after)
    assert predict_ladder(ix, _target(), 5, False) is None
    assert predict_new(ix, _target(), 5, False) is None
    # 하루 전과 365일 전은 들어감
    edge = [_sold(D0 - timedelta(days=1), 70), _sold(D0 - timedelta(days=365), 70)]
    ix = LadderIndex(edge + _many(4, 70))
    assert predict_ladder(ix, _target(), 6, False)["n"] == 6


def test_같은_날_캐시가_다음_날로_새지_않는다():
    ix = LadderIndex(_many(30, 70) + [_sold(D0, 99.0) for _ in range(30)])
    p1 = predict_ladder(ix, _target(), 10, False)  # D0
    t2 = _target()
    t2["sale_date"] = D0 + timedelta(days=1)
    p2 = predict_ladder(ix, t2, 10, False)  # 다음 날은 D0 낙찰이 비교 사례가 됨
    assert p1["n"] == 30 and p2["n"] == 60
