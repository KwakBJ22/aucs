"""① 지금 규칙을 운영과 같게: adjusted_rates 상한 · 유찰 횟수 정하기 · 지번 찾기 순서 · 역지오코딩 캐시 · k 맞추기."""

from collections import defaultdict
from datetime import date, timedelta

import pytest
from backtest import METHODS, assign_month_k
from geo import ApiError, coord_key, fill_cache, lookup, parse_result
from market import find_jibun, jibun_from_maejibun
from methods import build_sale_pool, fit_k, predict_rule, required_k
from table import candidate_rounds, choose_fallback, implied_rounds, pick_rounds, rate_sigungu

CATS6 = ("아파트", "빌라", "오피스텔", "상가", "땅", "그 밖")


def _sold(d: date, rate: float, **kw) -> dict:
    app = 100_000_000
    row = dict(
        result="sold", category="아파트", usage_raw="아파트", sido="11", sgg="11140", rate_sigungu="용산구",
        court_code="B000210", case_no="x", item_no=1, sale_date=d, failed_count=2, eff_failed=2,
        appraisal_krw=app, min_price_krw=64_000_000, winning_bid_krw=int(app * rate / 100),
        sale_rate=rate, min_rate=64.0, area_m2=84.0,
    )  # fmt: skip
    row.update(kw)
    return row


def _target(d: date, **kw) -> dict:
    row = _sold(d, 70.0, result="?", winning_bid_krw=None, sale_rate=None)
    row.update(kw)
    return row


# ---------- adjusted_rates: 지난 유찰가 위로 안 감 · 최저가 아래로 안 감 ----------
def test_예상은_지난_유찰가_위로_안_가고_최저가_아래로_안_간다():
    # 비슷한 물건은 95% 안팎에 팔렸지만, 최저가 64% · 저감 20% 면 지난 유찰가는 64÷0.8 = 80% — 거기까지만
    base = [_sold(date(2026, 9, 1) + timedelta(days=i), 93 + (i % 5)) for i in range(25)]
    p = predict_rule(base, _target(date(2026, 10, 1)), reduction_pct={"B000210": 20})
    assert p is not None
    assert p.p75 == pytest.approx(80_000_000)  # 지난 유찰가(80%)
    assert p.p50 == pytest.approx((64_000_000 + 80_000_000) / 2)  # 최저가와 지난 유찰가 사이 가운데
    assert p.p25 >= 64_000_000
    assert p.p25 <= p.p50 <= p.p75


def test_저감률을_모르면_30퍼센트로_셈한다():
    base = [_sold(date(2026, 9, 1) + timedelta(days=i), 95) for i in range(25)]
    p = predict_rule(base, _target(date(2026, 10, 1)), reduction_pct={})
    assert p.p75 == pytest.approx(64_000_000 / 0.7)  # 운영 last_failed_price 의 기본 30%


def test_관할_법원_차이만큼_옮긴다():
    # 같은 법원 사례가 지역 기준보다 3%p 이상 높고 30건 이상이면 그만큼 옮김(천장 80% 아래에서 확인)
    others = [
        _sold(date(2026, 9, 1) + timedelta(days=i % 40), 66, court_code="B000211")
        for i in range(40)
    ]
    mine = [
        _sold(date(2026, 9, 1) + timedelta(days=i % 40), 72, court_code="B000210")
        for i in range(35)
    ]
    pool = build_sale_pool(others + mine)
    red = {"B000210": 20, "B000299": 20}
    p = predict_rule([], _target(date(2026, 10, 15)), pool=pool, reduction_pct=red)
    q = predict_rule(
        [], _target(date(2026, 10, 15), court_code="B000299"), pool=pool, reduction_pct=red
    )  # 사례 없는 법원
    assert p is not None and q is not None
    assert q.p50 == pytest.approx(100_000_000 * 0.66, rel=0.02)  # 지역 가운데 그대로
    assert p.p50 > q.p50  # 같은 법원 차이(+6%p 안팎)만큼 옮김


def test_비교_사례는_운영과_같은_용도_이름과_유찰_횟수_칸으로_묶는다():
    # usage_raw 가 다르면(다세대 ↔ 연립) 따로, 유찰은 eff_failed 로(법원 숫자 failed_count 가 아니라)
    base = [
        _sold(
            date(2026, 9, 1) + timedelta(days=i),
            80,
            usage_raw="다세대",
            eff_failed=1,
            failed_count=9,
        )
        for i in range(30)
    ]
    target = _target(
        date(2026, 10, 1), usage_raw="다세대", eff_failed=1, failed_count=1, min_price_krw=1
    )
    pool = build_sale_pool(base)
    assert list(pool) == ["다세대"]
    p = predict_rule([], target, pool=pool)
    assert (
        p is not None and p.scope == "sigungu"
    )  # 법원 숫자(9) 가 아니라 eff_failed(1)로 같은 묶음
    other = _target(date(2026, 10, 1), usage_raw="연립주택", eff_failed=1, min_price_krw=1)
    assert predict_rule([], other, pool=pool) is None


# ---------- 유찰 횟수 정하기 ----------
PCT = {"B000210": 20.0}


def test_최저가로_센_유찰_횟수():
    assert implied_rounds("B000210", 100, 100, 3, PCT) == 0  # 최저가 = 감정가
    assert implied_rounds("B000210", 100, 64, 3, PCT) == 2  # 80% → 64%
    assert (
        implied_rounds("B000210", 100, 64, 2, PCT) is None
    )  # 법원 숫자보다 작지 않으면 안 씀(DB price_round 와 같음)
    assert implied_rounds("B000210", 100, 70, 5, PCT) is None  # 정수로 안 떨어짐
    assert implied_rounds("B999999", 100, 64, 5, PCT) is None  # 저감률 모르는 법원


def test_못_세면_가장_잘_맞은_후보를_쓴다():
    # 법원 숫자는 늘 1 크게 적혀 있고, 앞 기일 수는 모자란 자료
    samples = [(2, 3, 1), (1, 2, 0), (3, 4, 2), (0, 1, 0), (2, 3, 2)]
    best, rate = choose_fallback(samples)
    assert best == "yuchal-1" and rate["yuchal-1"] == 1.0 and rate["yuchal"] == 0.0
    assert candidate_rounds("yuchal-1", 4, 1) == 3 and candidate_rounds("prior", 4, 1) == 1
    n, how = pick_rounds("B999999", 100, 64, 4, 1, PCT, fallback="yuchal-1")
    assert n == 3 and "못 셈" in how
    n, how = pick_rounds("B000210", 100, 64, 4, 1, PCT, fallback="yuchal-1")
    assert n == 2 and how == "최저가로 셈"


def test_운영과_같은_시군구_묶음_글():
    assert rate_sigungu("수원시 권선구") == "수원시"
    assert rate_sigungu("강남구") == "강남구"
    assert rate_sigungu(None, "경기도 용인시 수지구 풍덕천동 1") == "용인시"


# ---------- 지번 찾는 순서 (a)(b)(c)(d) ----------
ITEMS = {("B000210", "2026타경1", 1): "서울특별시 강남구 신사동 617-2 신사빌 3층"}


def _inst(**kw) -> dict:
    row = dict(
        src="court", court_code="B000210", case_no="2026타경1", item_no=1, umd="신사동", jibun=None,
        maejibun=None, kx=314708.0, ky=547825.0, bldg_name="신사빌",
    )  # fmt: skip
    row.update(kw)
    return row


def test_지번_찾기_순서():
    cache = {"points": {coord_key(314708, 547825): {"umd": "도곡동", "jibun": "895-7"}}}
    # (a) maejibun 에 지번이 있으면 그것 — items · geo 보다 먼저
    assert find_jibun(_inst(maejibun="서울 강남구 논현동 12-3"), ITEMS, cache) == (
        "논현동",
        "12-3",
        "maejibun",
    )
    # 등기 설명(갑구 · 지분)은 지번이 아니다
    assert jibun_from_maejibun("갑구 57번 유자컴퍼니 주식회사 지분 246.8분의 6.430 전부") == (
        None,
        None,
    )
    # (b) 같은 법원 · 사건 · 물건번호가 core.items 에 있으면 그 주소의 지번
    assert find_jibun(_inst(), ITEMS, cache) == ("신사동", "617-2", "items")
    # (c) items 에 없으면 좌표 역지오코딩 결과(캐시)
    assert find_jibun(_inst(case_no="없는사건"), ITEMS, cache) == ("도곡동", "895-7", "geo")
    # (d) 그래도 없으면 지번 없이 이름 쪽(how='name')
    assert find_jibun(_inst(case_no="없는사건", kx=None, ky=None), ITEMS, cache) == (
        "신사동",
        None,
        "name",
    )
    assert find_jibun(_inst(case_no="없는사건"), ITEMS, {"points": {}})[2] == "name"


def test_브이월드_응답에서_법정동과_지번을_읽는다():
    res = {
        "result": [{"text": "서울특별시 강남구 도곡동 895-7", "structure": {"level5": "895-7전"}}]
    }
    assert parse_result(res) == ("도곡동", "895-7")
    assert parse_result({"result": []}) is None


# ---------- 역지오코딩 캐시: 두 번째는 안 물음 ----------
def test_역지오코딩_캐시는_두_번째에_안_묻는다():
    calls = []

    def fetch(x, y):
        calls.append((x, y))
        return None if x == 2 else ("신사동", "1-1")

    cache: dict = {"usage": {}, "points": {}}
    coords = [(1.0, 1.0), (2.0, 2.0), (1.0, 1.0)]  # 같은 좌표가 두 번 나와도 한 번만
    r1 = fill_cache(coords, cache, fetch, today=date(2026, 11, 27))
    assert r1["물은 수"] == 2 and len(calls) == 2
    r2 = fill_cache(coords, cache, fetch, today=date(2026, 11, 27))
    assert r2["물은 수"] == 0 and len(calls) == 2  # 못 찾은 좌표(None)도 다시 안 물음
    assert lookup(cache, 1.0, 1.0) == ("신사동", "1-1") and lookup(cache, 2.0, 2.0) is None


def test_역지오코딩은_하루_한도에서_멈추고_오류면_받은_데까지_남긴다():
    cache: dict = {"usage": {}, "points": {}}
    got = []
    coords = [(float(i), 0.0) for i in range(10)]
    r = fill_cache(
        coords,
        cache,
        lambda x, y: ("동", "1"),
        today=date(2026, 11, 27),
        daily_limit=3,
        save=got.append,
    )
    assert r["물은 수"] == 3 and r["남은 수"] == 7 and r["멈춤"] == "하루 한도"
    assert cache["usage"]["2026-11-27"] == 3 and got  # 저장도 함
    r = fill_cache(
        coords, cache, lambda x, y: ("동", "1"), today=date(2026, 11, 28), daily_limit=100
    )
    assert r["물은 수"] == 7  # 다음 날은 이어서

    def boom(x, y):
        if x >= 2:
            raise ApiError("한도")
        return ("동", "1")

    c2: dict = {"usage": {}, "points": {}}
    r = fill_cache([(float(i), 0.0) for i in range(5)], c2, boom, today=date(2026, 11, 27))
    assert r["물은 수"] == 2 and "오류" in r["멈춤"] and len(c2["points"]) == 2


# ---------- k 맞추기는 미래 달을 안 봄 ----------
def _rec(method="①지금 규칙", cat="아파트", actual=100.0, lo=90.0, mid=100.0, hi=110.0) -> dict:
    return dict(
        method=method, cat=cat, lo=lo, mid=mid, hi=hi, actual=actual, floor=None, lo_adj=None, hi_adj=None, k=None
    )  # fmt: skip


def test_k는_지난_성적으로_범위_안이_절반이_되게_정한다():
    # 필요한 배수가 0.5 · 1.5 · 2.5 · 3.5 인 물건 40건 → 가운데 값이 k
    hist = [_rec(actual=100 + 10 * (0.5 + (i % 4))) for i in range(40)]
    k = fit_k(hist)
    assert k == pytest.approx(2.0)  # 20번째 · 21번째 값(1.5 와 2.5)의 가운데
    inside = sum(1 for h in hist if required_k(h["lo"], h["mid"], h["hi"], h["actual"]) <= k)
    assert inside == 20  # 정확히 절반
    assert fit_k(hist[:29]) is None  # 지난 성적 30건 미만이면 안 맞춤


def test_k는_이번_달과_미래_값에_영향을_안_받는다():
    history = {(m, c): [] for m in METHODS for c in CATS6}
    history[("①지금 규칙", "아파트")] = [_rec(actual=100 + 10 * (0.5 + (i % 4))) for i in range(40)]
    this_month_a = [_rec(actual=100.0), _rec(actual=100.0)]
    this_month_b = [_rec(actual=100000.0), _rec(actual=-5000.0)]  # 이번 달 값이 아주 달라도
    kt_a, kt_b = defaultdict(dict), defaultdict(dict)
    assign_month_k(this_month_a, history, kt_a, "2026-10")
    assign_month_k(this_month_b, history, kt_b, "2026-10")
    assert this_month_a[0]["k"] == pytest.approx(this_month_b[0]["k"]) == pytest.approx(2.0)
    assert kt_a["①지금 규칙|아파트"]["2026-10"] == kt_b["①지금 규칙|아파트"]["2026-10"]
    assert (
        len(history[("①지금 규칙", "아파트")]) == 40
    )  # 이번 달 행을 history 에 넣는 것은 부른 쪽이 달이 끝난 뒤에
    # 지난 성적이 모자란 방식 · 종류는 안 맞춤
    other = [_rec(method="②시세 기준", cat="빌라")]
    assign_month_k(other, history, defaultdict(dict), "2026-10")
    assert other[0]["k"] is None and other[0]["lo_adj"] is None
    # 최저가 밑으로는 안 내려감
    rec = [_rec(lo=60.0, mid=100.0, hi=110.0)]
    rec[0]["floor"] = 95.0
    assign_month_k(rec, history, defaultdict(dict), "2026-10")
    assert rec[0]["lo_adj"] >= 95.0
