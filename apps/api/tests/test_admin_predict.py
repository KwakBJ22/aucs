"""관리자 낙찰가 예측: 나눠 보기(score_split) · 그림자 시세 기준(shadow_market) — 순수 함수 시험."""

from datetime import date, timedelta

from aucs_api.services.admin_predict import (
    MIN_POOL,
    fail_bucket,
    kind_of,
    score_split,
    shadow_market,
)

D0 = date(2026, 11, 10)


def row(d: date = D0, *, win: int = 80, market: int | None = 100, usage: str = "아파트", failed: int = 1,
        address: str = "서울특별시 강남구 역삼동 1", app: int = 100, mn: int = 50, rate: float | None = None,
        small: bool = False, new: bool = False) -> dict:  # fmt: skip
    """한 낙찰 줄(단위는 임의 — 감정가 100 · 시세 100 · 낙찰가 80 이면 ratio 0.8)."""
    return {
        "sale_date": d, "usage_name": usage, "failed_count": failed,
        "sale_rate": win / app * 100 if rate is None else rate, "p25": 60.0, "p50": 70.0, "p75": 80.0,
        "small_sample": small, "new_item": new, "appraisal_krw": app, "min_price_krw": mn,
        "winning_bid_krw": win, "market_krw": market, "address": address,
    }  # fmt: skip


def pool(n: int, *, days_before: int = 10, win: int = 80, **kw) -> list[dict]:
    """비교 사례용 낙찰(성적표 대상이 아니게 처음 나온 물건 표시 — 풀로만 쓰임)."""
    kw.setdefault("new", True)
    return [row(D0 - timedelta(days=days_before + i % 30), win=win, **kw) for i in range(n)]


def test_종류와_유찰_묶음():
    assert kind_of("아파트") == "아파트"
    assert {kind_of(x) for x in ("다세대", "연립주택,다세대,빌라", "연립주택")} == {"빌라"}
    assert kind_of("오피스텔") == "오피스텔"
    assert kind_of("근린시설") == kind_of("상가,오피스텔,근린시설") == kind_of("판매시설") == "상가"
    assert kind_of("임야") == kind_of("전답") == kind_of("대지") == "땅"
    assert kind_of("기타") == "그 밖"
    assert [fail_bucket(n) for n in (None, 0, 1, 2, 3, 7)] == [0, 0, 1, 2, 3, 3]


def test_나눠_보기_칸_성적과_표본_적음():
    inside = [
        row(win=70) for _ in range(10)
    ]  # 낙찰가율 70 — 범위(60~80) 안, 예상 가운데 70 과 같음
    low = [row(win=50) for _ in range(3)]  # 범위 아래
    high = [row(win=90) for _ in range(2)]  # 범위 위
    cell = score_split(inside + low + high)
    assert len(cell) == 1 and cell[0]["kind"] == "아파트" and cell[0]["g"] == 1
    assert cell[0]["n"] == 15 and cell[0]["few"] is False
    assert cell[0]["inside"] == round(100 * 10 / 15, 1)
    assert cell[0]["below"] == 20.0 and cell[0]["above"] == round(100 * 2 / 15, 1)
    # 가운데 오차의 가운데 값: 10건은 0%, 낙찰가 50 은 |50−70|/50 = 40%, 90 은 22.2% → 15건의 가운데(8번째)는 0
    assert cell[0]["mid_err"] == 0.0
    # 15건 미만 칸은 건수만
    few = score_split([row(win=70) for _ in range(14)])
    assert few == [{"kind": "아파트", "g": 1, "n": 14, "few": True}]


def test_나눠_보기는_성적표와_같은_거르기():
    rows = [row(failed=0), row(small=True), row(new=True), row(rate=None, win=70)]
    rows[3]["sale_rate"] = None
    assert score_split(rows) == []  # 유찰 0 · 표본 적음 · 처음 나온 물건 · 낙찰가율 없음은 뺌
    g3 = score_split([row(failed=5, win=70) for _ in range(15)])
    assert g3[0]["g"] == 3  # 3회 이상은 한 칸


# ---------- 그림자: 풀 30건 미만이면 제외 ----------
def _one(res: dict, kind: str = "아파트") -> dict:
    (r,) = [x for x in res["rows"] if x["kind"] == kind]
    return r


def test_풀이_30건_미만이면_제외():
    target = row(win=80)
    r = _one(shadow_market(pool(MIN_POOL - 1) + [target]))
    assert r["excluded"] == 1 and r["shadow"] == {"n": 0} and r["current"] == {"n": 0}
    r = _one(shadow_market(pool(MIN_POOL) + [target]))
    assert r["excluded"] == 0 and r["shadow"]["n"] == 1 and r["current"]["n"] == 1  # 같은 물건끼리


def test_시세가_없는_낙찰은_대상도_풀도_아니다():
    rows = pool(MIN_POOL, market=None) + [row(market=None)]
    assert shadow_market(rows)["rows"] == []
    # 시세 있는 풀 + 시세 없는 대상 → 대상 아님
    assert shadow_market(pool(MIN_POOL) + [row(market=None)])["rows"] == []


# ---------- 최저가 밑으로 안 감 ----------
def test_그림자_범위는_최저가_밑으로_안_간다():
    # 풀 ratio 0.3 → 그림자 범위 시세 × 0.3 = 30, 최저가가 55 이면 셋 다 55 로 올라감 → 낙찰가 80 은 범위 위(높게)
    rows = pool(MIN_POOL, win=30) + [row(win=80, mn=55)]
    r = _one(shadow_market(rows))
    assert r["shadow"]["above"] == 100.0 and r["shadow"]["inside"] == 0.0
    assert r["shadow"]["mid_err"] == round(100 * abs(80 - 55) / 80, 1)  # 가운데 = 최저가 55
    # 최저가를 낮추면 30 그대로(범위 아래)
    r = _one(shadow_market(pool(MIN_POOL, win=30) + [row(win=80, mn=10)]))
    assert r["shadow"]["mid_err"] == round(100 * abs(80 - 30) / 80, 1)


# ---------- 입찰일 당일 · 뒤 낙찰은 풀에 안 들어감 ----------
def test_입찰일_당일과_뒤_낙찰은_풀에_안_들어간다():
    target = row(win=80)
    older = pool(MIN_POOL - 1)  # 29건 — 하나 모자람
    same_day = row(D0, win=80, new=True)
    after = [row(D0 + timedelta(days=k), win=80, new=True) for k in range(1, 5)]
    r = _one(shadow_market(older + [same_day, *after, target]))
    # 당일 · 뒤를 풀로 쳤다면 29+1+4 ≥ 30 이라 셈이 됐을 것 — 안 들어가므로 제외
    assert r["excluded"] >= 1 and r["shadow"]["n"] == 0
    # 일 년(365일)보다 오래된 것도 안 들어감
    old = [row(D0 - timedelta(days=366 + i), win=80, new=True) for i in range(40)]
    assert _one(shadow_market(old + [target]))["shadow"]["n"] == 0
    # 딱 하루 전은 들어감
    day_before = [row(D0 - timedelta(days=1), win=80, new=True) for _ in range(MIN_POOL)]
    assert _one(shadow_market(day_before + [target]))["shadow"]["n"] == 1


# ---------- 시도 30건 미만이면 전국으로 넓힘 ----------
def test_시도가_30건_미만이면_전국으로_넓힌다():
    seoul = pool(10, win=60, address="서울특별시 강남구 1")
    gyeonggi = pool(40, win=90, address="경기도 수원시 1")
    target = row(win=60, address="서울특별시 강남구 9", mn=10)
    # 서울 10건뿐 → 전국 50건(0.6 열 건 + 0.9 마흔 건)의 분위수 → 가운데 0.9
    r = _one(shadow_market(seoul + gyeonggi + [target]))
    assert r["shadow"]["n"] == 1 and r["shadow"]["mid_err"] == round(100 * abs(60 - 90) / 60, 1)
    # 서울이 30건 이상이면 서울만(0.6) → 오차 0
    seoul30 = pool(30, win=60, address="서울특별시 강남구 1")
    r = _one(shadow_market(seoul30 + gyeonggi + [target]))
    assert r["shadow"]["mid_err"] == 0.0


def test_종류와_유찰_묶음이_다르면_풀에_안_섞인다():
    rows = pool(MIN_POOL, usage="다세대") + pool(MIN_POOL, failed=2) + [row(win=80)]
    assert _one(shadow_market(rows))["excluded"] == 1  # 아파트·유찰1 풀이 없음


def test_달마다_종류마다_합계():
    rows = pool(MIN_POOL) + [row(D0, win=80), row(D0 + timedelta(days=40), win=80)]
    res = shadow_market(rows)["rows"]
    months = {(x["month"], x["kind"]) for x in res}
    assert (
        ("2026-11", "아파트") in months
        and ("2026-11", "전체") in months
        and ("2026-12", "전체") in months
    )
