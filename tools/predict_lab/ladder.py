"""강사님 장부(설계서 법원판 낙찰예측장부 5-2 · 5-3)의 방식을 다시 만든 ④ 새 방식 · ⑤ 사다리 (순수 함수).

- 회차: 법원 유찰 횟수 칸은 안 믿고, 최저가율을 저감 사다리 (1−저감률)^회차 에 맞춰 거꾸로 센다(0~8회, 2%p 넘게 어긋나면 못 셈).
- ④ 새 방식: 칸 = 용도군(실험실 종류 6개) × 저감률 × 회차. 같은 관할 법원 표본이 N건 이상이면 법원 칸, 아니면 법원 없이 그 칸.
- ⑤ 사다리: 구(시군구) → 관할 법원 → 용도군 전체 → 전 용도 순서로, 같은 저감률 · 회차 안에서 표본이 N건 찰 때까지 넓힘.
- 비교 사례는 맞힐 물건의 입찰일 앞선 365일 안 낙찰만(당일 · 뒤는 안 넣음). 이상치(나): 비교 사례의 낙찰가율에서
  사분위 범위 1.5배 밖을 뺌(맞힐 물건은 그대로).
"""

from __future__ import annotations

from bisect import bisect_left
from collections import defaultdict
from datetime import date, timedelta

from methods import quantile

MAX_ROUND = 8
LADDER_TOL = 2.0  # 최저가율과 사다리 값의 차이가 이보다 크면 「못 셈」(%p)
WINDOW_DAYS = 365
FLOOR_N = 5  # 어느 단에서도 N건이 안 차도, 가장 넓은 단이 이 건수 이상이면 그걸로 냄(그보다 적으면 표본 부족 → 뺌) [Claude 판단]
SCOPES = ("구", "법원", "용도군", "전 용도")  # ⑤ 사다리 단(좁은 것부터). ④ 는 「법원 칸」 · 「칸」


def ladder_round(min_rate: float | None, pct: float | None) -> int | None:
    """최저가율(감정가 대비 %)을 저감률 pct(%)의 사다리 100·(1−pct/100)^회차 에 가장 가까운 회차(0~8)로. 2%p 넘게 어긋나면 None."""
    if min_rate is None or pct is None or not 0 < pct < 100:
        return None
    best: tuple[float, int] | None = None
    for r in range(MAX_ROUND + 1):
        d = abs(min_rate - 100 * (1 - pct / 100) ** r)
        if best is None or d < best[0]:
            best = (d, r)
    assert best is not None
    return best[1] if best[0] <= LADDER_TOL else None


def add_ladder_rounds(rows: list[dict], pct_by_court: dict[str, float]) -> dict:
    """각 줄에 ladder_pct · ladder_round(못 셈이면 None)를 붙이고, 센 결과를 돌려준다.
    돌려주는 값: 못 셈 건수(까닭별) · 세진 줄 중 지금 쓰는 회차(eff_failed)와 같은 비율 · 종류별."""
    stat: dict = {
        "줄": 0,
        "셈": 0,
        "못 셈": 0,
        "저감률 모르는 법원": 0,
        "사다리에서 2%p 넘게 벗어남": 0,
    }
    same = {"eff_failed": [0, 0], "price_round(우리 자료)": [0, 0]}
    by_cat: dict[str, list[int]] = defaultdict(lambda: [0, 0])  # 종류 → [줄, 못 셈]
    for r in rows:
        pct = pct_by_court.get(r["court_code"])
        r["ladder_pct"] = pct
        rd = ladder_round(r.get("min_rate"), pct)
        r["ladder_round"] = rd
        stat["줄"] += 1
        by_cat[r["category"]][0] += 1
        if rd is None:
            stat["못 셈"] += 1
            by_cat[r["category"]][1] += 1
            stat["저감률 모르는 법원" if pct is None else "사다리에서 2%p 넘게 벗어남"] += 1
            continue
        stat["셈"] += 1
        if r.get("eff_failed") is not None:
            same["eff_failed"][1] += 1
            same["eff_failed"][0] += r["eff_failed"] == rd
        if r.get("price_round") is not None:
            same["price_round(우리 자료)"][1] += 1
            same["price_round(우리 자료)"][0] += r["price_round"] == rd
    stat["지금 쓰는 회차와 같은 비율"] = {
        k: {"같음": a, "비교한 줄": b, "%": round(100 * a / b, 1) if b else None}
        for k, (a, b) in same.items()
    }
    stat["종류별 못 셈"] = {c: {"줄": a, "못 셈": b} for c, (a, b) in sorted(by_cat.items())}
    return stat


def trim_iqr(xs: list[float]) -> list[float]:
    """사분위 범위 1.5배 밖을 뺀다. xs 는 정렬된 목록. 4건 미만이면 그대로."""
    if len(xs) < 4:
        return xs
    q1, q3 = quantile(xs, 0.25), quantile(xs, 0.75)
    lo, hi = q1 - 1.5 * (q3 - q1), q3 + 1.5 * (q3 - q1)
    return [x for x in xs if lo <= x <= hi]


class LadderIndex:
    """낙찰 줄을 (키 → 날짜순 낙찰가율) 로 색인해, 입찰일 앞선 365일 안 낙찰가율 목록을 빨리 꺼낸다.
    키 종류: gu(종류·저감률·회차·시군구) · court(…·법원) · cell(종류·저감률·회차) · all(저감률·회차)."""

    def __init__(self, rows: list[dict]):
        self._dates: dict[tuple, list[date]] = defaultdict(list)
        self._rates: dict[tuple, list[float]] = defaultdict(list)
        for r in sorted(rows, key=lambda x: x["sale_date"]):
            if r["result"] != "sold" or r["sale_rate"] is None or r.get("ladder_round") is None:
                continue
            for key in self.keys(r).values():
                self._dates[key].append(r["sale_date"])
                self._rates[key].append(float(r["sale_rate"]))
        self._cache: dict[tuple, list[float]] = {}
        self._cache_day: date | None = None

    @staticmethod
    def keys(r: dict) -> dict[str, tuple]:
        c, p, rd = r["category"], r["ladder_pct"], r["ladder_round"]
        return {
            "gu": ("gu", c, p, rd, r.get("sgg")),
            "court": ("court", c, p, rd, r["court_code"]),
            "cell": ("cell", c, p, rd),
            "all": ("all", p, rd),
        }

    def pool(self, key: tuple, day: date, trim: bool) -> list[float]:
        """입찰일 day 앞선 365일 안(당일 · 뒤 제외) 낙찰가율, 작은 것부터. 같은 날은 캐시를 씀."""
        if self._cache_day != day:
            self._cache.clear()
            self._cache_day = day
        ck = (key, trim)
        hit = self._cache.get(ck)
        if hit is not None:
            return hit
        ds = self._dates.get(key, [])
        lo = bisect_left(ds, day - timedelta(days=WINDOW_DAYS))
        hi = bisect_left(ds, day)  # day 당일 · 뒤는 안 들어감
        xs = sorted(self._rates[key][lo:hi]) if hi > lo else []
        out = trim_iqr(xs) if trim else xs
        self._cache[ck] = out
        return out


def _pred(target: dict, xs: list[float], scope: str) -> dict:
    app = float(target["appraisal_krw"])
    mn = target.get("min_price_krw")
    q = {
        k: quantile(xs, v)
        for k, v in (("p10", 0.10), ("p25", 0.25), ("p50", 0.50), ("p75", 0.75), ("p90", 0.90))
    }
    amt = {k: max(app * v / 100, float(mn)) if mn else app * v / 100 for k, v in q.items()}
    return {
        "lo": amt["p25"], "mid": amt["p50"], "hi": amt["p75"], "p10": amt["p10"], "p90": amt["p90"],
        "n": len(xs), "scope": scope,
    }  # fmt: skip


def _ok(target: dict) -> bool:
    return bool(
        target.get("ladder_round") is not None
        and target.get("appraisal_krw")
        and target.get("sale_date")
    )


def predict_new(index: LadderIndex, target: dict, n_min: int, trim: bool) -> dict | None:
    """④ 새 방식: 법원 칸(같은 관할 법원 표본 n_min 건 이상) → 아니면 법원 없이 그 칸. 회차를 못 셌으면 None."""
    if not _ok(target):
        return None
    k = index.keys(target)
    day = target["sale_date"]
    xs = index.pool(k["court"], day, trim)
    if len(xs) >= n_min:
        return _pred(target, xs, "법원 칸")
    xs = index.pool(k["cell"], day, trim)
    if len(xs) >= max(FLOOR_N, 1):
        return _pred(target, xs, "칸")
    return None  # 칸에 표본이 너무 적음(표본 부족)


def predict_ladder(index: LadderIndex, target: dict, n_min: int, trim: bool) -> dict | None:
    """⑤ 사다리: 구 → 관할 법원 → 용도군 전체 → 전 용도, 표본 n_min 건이 차는 첫 단. 끝까지 안 차면 가장 넓은 단이
    FLOOR_N 건 이상일 때 그것, 아니면 None(표본 부족). 어느 단을 썼는지 scope 에 남김."""
    if not _ok(target):
        return None
    k = index.keys(target)
    day = target["sale_date"]
    last: list[float] = []
    for scope, key in zip(SCOPES, (k["gu"], k["court"], k["cell"], k["all"]), strict=True):
        xs = index.pool(key, day, trim)
        if len(xs) >= n_min:
            return _pred(target, xs, scope)
        last = xs
    if len(last) >= FLOOR_N:
        return _pred(target, last, SCOPES[-1] + "(N 미달)")
    return None
