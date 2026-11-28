"""처음 나온 물건(회차 0) 따로: 회차 0 만 고름 · 감정가 밑으로 안 감 · 구간 20건 미만이면 이웃과 합침 · ⑥+⑤ 섞음 · 미래 섞임 없음."""

from datetime import date, timedelta

import pytest
from backtest_new import _clip_rec, compare
from newitem import (
    MIN_BAND,
    MIN_POOL,
    NewItemIndex,
    band_of,
    band_table,
    clip_floor,
    merge_bands,
    mix_band_ladder,
    new_targets,
    p_sold_band,
    predict_band,
    predict_market_new,
)

D0 = date(2026, 10, 15)
APP = 100_000_000


def _row(
    d: date,
    *,
    win_over_mkt: float = 1.1,
    app_over_mkt: float = 1.0,
    result="sold",
    rd=0,
    sido="11",
    cat="아파트",
) -> dict:
    """한 줄: 시세 = 감정가 ÷ app_over_mkt, 낙찰가 = 시세 × win_over_mkt."""
    mkt = int(APP / app_over_mkt)
    win = int(mkt * win_over_mkt) if result == "sold" else None
    return dict(
        result=result, ladder_round=rd, category=cat, sale_date=d, appraisal_krw=APP, market_price_krw=mkt,
        winning_bid_krw=win, sale_rate=win * 100 / APP if win else None, sido=sido, min_price_krw=APP,
    )  # fmt: skip


def _many(n: int, **kw) -> list[dict]:
    return [_row(D0 - timedelta(days=1 + i % 60), **kw) for i in range(n)]


def _target(**kw) -> dict:
    return _row(D0, result="failed", **kw)  # 맞힐 물건(낙찰가는 쓰지 않음)


# ---------- 회차 0 만 고름 ----------
def test_회차_0_만_고른다():
    rows = [_row(D0, rd=0), _row(D0, rd=1), _row(D0, rd=None), _row(D0 - timedelta(days=100), rd=0)]
    got = new_targets(rows, D0)
    assert len(got) == 1 and got[0]["ladder_round"] == 0 and got[0]["sale_date"] == D0


def test_비교_사례도_회차_0_만():
    ix = NewItemIndex(_many(40, rd=1) + _many(MIN_POOL, rd=0))
    p = predict_market_new(ix, _target())
    assert p is not None and p["n"] == MIN_POOL  # 회차 1 낙찰 40건은 안 섞임
    assert predict_market_new(NewItemIndex(_many(40, rd=1)), _target()) is None


# ---------- 감정가 밑으로 안 감 ----------
def test_가격_범위는_감정가_밑으로_안_간다():
    assert clip_floor({"lo": 90.0, "mid": 100.0, "hi": 120.0}, 100.0) == {
        "lo": 100.0,
        "mid": 100.0,
        "hi": 120.0,
    }
    assert clip_floor(None, 100.0) is None
    # 낙찰가 ÷ 시세 = 0.7 인 사례만 있어도(= 감정가의 70%) 범위는 감정가(1억) 이상
    ix = NewItemIndex(_many(MIN_POOL, win_over_mkt=0.7))
    for p in (predict_market_new(ix, _target()), predict_band(ix, _target())):
        assert p is not None and p["lo"] >= APP and p["mid"] >= APP and p["hi"] >= APP


def test_채점_행도_감정가_밑으로_안_간다():
    rec = {
        "lo": 80.0,
        "mid": 90.0,
        "hi": 110.0,
        "actual": 120.0,
        "actual_ratio": 120.0,
        "pred_mid_ratio": 90.0,
    }
    out = _clip_rec(rec)  # 감정가 = 낙찰가 ÷ 낙찰가율 = 100
    assert (out["lo"], out["mid"], out["hi"]) == (100.0, 100.0, 110.0) and out[
        "pred_mid_ratio"
    ] == 100.0


# ---------- 구간 20건 미만이면 이웃과 합침 ----------
def test_구간_나누기():
    assert [band_of(x) for x in (0.5, 0.8, 0.85, 0.9, 0.99, 1.0, 1.09, 1.1, 2.0)] == [
        0,
        1,
        1,
        2,
        2,
        3,
        3,
        4,
        4,
    ]


def test_구간_표본이_모자라면_이웃과_합친다():
    assert merge_bands([5, 30, 5, 5, 5], 1) == (1, 1)  # 이미 20건 이상
    assert merge_bands([5, 5, 30, 5, 5], 0) == (0, 2)  # 0 → 이웃 1(5) → 2(30)
    assert merge_bands([10, 6, 3, 9, 8], 2) == (
        2,
        4,
    )  # 3 → 이웃 중 많은 쪽(9) 12 → 다시 많은 쪽(8) 20
    assert merge_bands([3, 3, 3, 3, 3], 2) is None  # 다 합쳐도 20건 미만
    assert MIN_BAND == 20


def test_구간_20건_미만이면_이웃_구간과_합쳐_낸다():
    rows = _many(25, app_over_mkt=0.95) + _many(
        10, app_over_mkt=1.05, win_over_mkt=1.2
    )  # 1.0~1.1 은 10건뿐
    ix = NewItemIndex(rows)
    p = predict_band(ix, _target(app_over_mkt=1.05))
    assert p is not None and "합침" in p["scope"] and p["n"] == 35
    p = predict_band(ix, _target(app_over_mkt=0.95))  # 0.9~1.0 은 25건 — 합치지 않음
    assert p["scope"] == "0.9~1.0" and p["n"] == 25


# ---------- ⑥+⑤ 섞음 ----------
def test_섞음은_시세_있으면_6_없으면_5():
    p5, p6 = {"mid": 5}, {"mid": 6}
    assert mix_band_ladder(p6, p5) is p6
    assert mix_band_ladder(None, p5) is p5
    ix = NewItemIndex(_many(40))
    no_market = _target()
    no_market["market_price_krw"] = None
    assert predict_band(ix, no_market) is None and predict_market_new(ix, no_market) is None
    assert mix_band_ladder(predict_band(ix, no_market), p5) is p5  # 시세 없는 물건 → ⑤


# ---------- ② 30건 미만이면 시도 → 전국 → 제외 ----------
def test_시세_기준은_시도_전국_제외_순서():
    rows = _many(10, sido="11", win_over_mkt=1.0) + _many(40, sido="41", win_over_mkt=1.3)
    ix = NewItemIndex(rows)
    p = predict_market_new(ix, _target(sido="11"))  # 서울 10건 < 30 → 전국 50건
    assert p["scope"] == "전국" and p["n"] == 50
    rows = _many(MIN_POOL, sido="11", win_over_mkt=1.0) + _many(40, sido="41", win_over_mkt=1.3)
    p = predict_market_new(NewItemIndex(rows), _target(sido="11"))
    assert p["scope"] == "시도" and p["n"] == MIN_POOL and p["mid"] == pytest.approx(APP, rel=0.01)
    assert (
        predict_market_new(NewItemIndex(_many(MIN_POOL - 1)), _target()) is None
    )  # 전국도 모자라면 제외


# ---------- 미래 섞임 없음 ----------
def test_입찰일_당일_뒤_365일_넘은_낙찰은_비교_사례가_아니다():
    old = [_row(D0 - timedelta(days=366 + i)) for i in range(40)]
    same_day = [_row(D0) for _ in range(40)]
    after = [_row(D0 + timedelta(days=1 + i)) for i in range(40)]
    ix = NewItemIndex(old + same_day + after)
    assert predict_market_new(ix, _target()) is None
    assert predict_band(ix, _target()) is None
    assert p_sold_band(ix, _target()) is None
    edge = [_row(D0 - timedelta(days=1)), _row(D0 - timedelta(days=365))]
    assert len(NewItemIndex(edge + _many(MIN_POOL - 2)).window("아파트", D0)) == MIN_POOL


def test_팔릴_확률_구간별_비율():
    rows = _many(15, result="sold", app_over_mkt=1.05) + _many(
        45, result="failed", app_over_mkt=1.05
    )
    assert p_sold_band(NewItemIndex(rows), _target(app_over_mkt=1.05)) == pytest.approx(0.25)
    assert (
        p_sold_band(NewItemIndex(rows[:10]), _target(app_over_mkt=1.05)) is None
    )  # 다 합쳐도 20건 미만


def test_구간표는_회차_0_시세_붙은_줄만():
    rows = (
        _many(5, app_over_mkt=1.2)
        + _many(3, app_over_mkt=1.2, result="failed")
        + _many(4, rd=1, app_over_mkt=1.2)
    )
    t = band_table(rows)
    top = t[-1]
    assert top["신건"] == 8 and top["낙찰"] == 5 and top["팔린 비율 %"] == 62.5


# ---------- 같은 물건끼리 · 50건 미만이면 이긴 방식 안 정함 ----------
def _rec(mid: float) -> dict:
    return dict(
        lo=mid - 5,
        mid=mid,
        hi=mid + 5,
        actual=100.0,
        pred_mid_ratio=mid,
        actual_ratio=100.0,
        lo_adj=None,
    )


def test_같은_물건_50건_미만이면_이긴_방식을_안_정한다():
    def items(n: int) -> dict:
        return {f"i{k}": {"A": _rec(98.0), "B": _rec(90.0)} for k in range(n)}

    g = compare(items(49), ("A", "B"))
    assert (
        g["few"] and g["이긴 방식"] is None and g["stats"]["A"]["평균 오차 %p"] == 2.0
    )  # 숫자는 참고로 냄
    g = compare(items(50), ("A", "B"))
    assert not g["few"] and g["이긴 방식"] == "A"
    # 한 방식이 값을 안 낸 물건은 같은 물건에서 빠짐
    half = items(60)
    for k in range(20):
        del half[f"i{k}"]["B"]
    assert compare(half, ("A", "B"))["건수"] == 40
