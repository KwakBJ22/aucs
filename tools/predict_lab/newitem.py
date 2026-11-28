"""처음 나온 물건(회차 0 — 최저가율로 센 회차) 따로: 낙찰가율 통계 대신 시세 · 감정가 차이를 쓰는 방식 (순수 함수).

- 처음 나온 물건은 최저가 = 감정가라 낙찰은 감정가 이상으로 팔린다 → 가격 범위는 감정가 밑으로 안 감.
- ② 시세 기준(신건판): 같은 종류 · 회차 0 · 시세 있는 낙찰의 「낙찰가 ÷ 시세」 25·50·75%. 30건 미만이면 시도 → 전국 → 제외.
- ⑥ 감정가 ÷ 시세 구간: 같은 종류 회차 0 낙찰을 감정가 ÷ 시세 구간(0.8 미만 · 0.8~0.9 · 0.9~1.0 · 1.0~1.1 · 1.1 이상)으로
  나눠 그 구간의 낙찰가율(감정가 대비) 25·50·75%. 구간 표본 20건 미만이면 이웃 구간과 합침.
- ⑥+⑤ 섞음: 시세가 있어 ⑥ 이 나오면 ⑥, 아니면 ⑤.
- 비교 사례는 맞힐 물건의 입찰일 앞선 365일 안(당일 · 뒤 안 넣음) 낙찰만.
"""

from __future__ import annotations

from bisect import bisect_left
from collections import defaultdict
from datetime import date, timedelta
from typing import Any, NamedTuple

from methods import quantile

BAND_EDGES = (0.8, 0.9, 1.0, 1.1)
BAND_LABELS = ("0.8 미만", "0.8~0.9", "0.9~1.0", "1.0~1.1", "1.1 이상")
MIN_POOL = 30  # ② 비교 사례 최소 건수(시도 → 전국)
MIN_BAND = 20  # ⑥ 구간 표본 최소 건수(모자라면 이웃 구간과 합침)
WINDOW_DAYS = 365


def band_of(app_over_market: float) -> int:
    """감정가 ÷ 시세 → 구간 번호 0~4 (0.8 이상이면 1, 0.9 이상이면 2, … 경계값은 위 구간)."""
    return sum(1 for e in BAND_EDGES if app_over_market >= e)


def merge_bands(counts: list[int], band: int, min_n: int = MIN_BAND) -> tuple[int, int] | None:
    """구간 band 의 표본이 min_n 건 미만이면 이웃 구간을 하나씩 합친다(건수가 많은 이웃부터, 같으면 낮은 쪽).
    돌려주는 값: 합친 구간 범위 (lo, hi) 양 끝 포함. 전 구간을 합쳐도 min_n 건 미만이면 None."""
    lo = hi = band
    while sum(counts[lo : hi + 1]) < min_n:
        left = counts[lo - 1] if lo > 0 else None
        right = counts[hi + 1] if hi < len(counts) - 1 else None
        if left is None and right is None:
            return None
        if right is None or (left is not None and left >= right):
            lo -= 1
        else:
            hi += 1
    return lo, hi


def new_targets(rows: list[dict], start: date) -> list[dict]:
    """처음 나온 물건 = 최저가율로 센 회차가 0 인 줄(낙찰 · 유찰 모두), start 이후 매각일."""
    return [r for r in rows if r.get("ladder_round") == 0 and r["sale_date"] >= start]


def clip_floor(p: dict | None, app: float) -> dict | None:
    """가격 범위는 감정가 밑으로 안 감(처음 나온 물건은 최저가 = 감정가)."""
    if p is None:
        return None
    out = dict(p)
    for k in ("lo", "mid", "hi", "p10", "p90"):
        if k in out:
            out[k] = max(out[k], app)
    return out


class _E(NamedTuple):
    day: date
    sold: bool
    rate: float | None  # 낙찰가율(감정가 대비 %) — 낙찰만
    win_over_mkt: float | None  # 낙찰가 ÷ 시세 — 낙찰만
    band: int
    sido: str | None


class NewItemIndex:
    """회차 0 · 시세 있는 줄(낙찰 · 유찰)을 종류별 날짜순으로 색인 — 입찰일 앞선 365일 안 목록을 꺼낸다."""

    def __init__(self, rows: list[dict]):
        by: dict[str, list[_E]] = defaultdict(list)
        for r in sorted(rows, key=lambda x: x["sale_date"]):
            if (
                r.get("ladder_round") != 0
                or not r.get("market_price_krw")
                or not r.get("appraisal_krw")
            ):
                continue
            if r["result"] == "sold":
                if r.get("sale_rate") is None or not r.get("winning_bid_krw"):
                    continue
                e = _E(
                    r["sale_date"], True, float(r["sale_rate"]), r["winning_bid_krw"] / r["market_price_krw"],
                    band_of(r["appraisal_krw"] / r["market_price_krw"]), r.get("sido"),
                )  # fmt: skip
            elif r["result"] == "failed":
                e = _E(
                    r["sale_date"],
                    False,
                    None,
                    None,
                    band_of(r["appraisal_krw"] / r["market_price_krw"]),
                    r.get("sido"),
                )
            else:
                continue
            by[r["category"]].append(e)
        self._by = by
        self._days = {c: [e.day for e in v] for c, v in by.items()}

    def window(self, cat: str, day: date) -> list[_E]:
        """입찰일 day 앞선 365일 안(당일 · 뒤 제외)."""
        ds = self._days.get(cat, [])
        lo = bisect_left(ds, day - timedelta(days=WINDOW_DAYS))
        hi = bisect_left(ds, day)
        return self._by.get(cat, [])[lo:hi]


def _amounts(app: float, rates: list[float], n: int, scope: str) -> dict[str, Any]:
    q = {k: app * quantile(rates, v) / 100 for k, v in (("lo", 0.25), ("mid", 0.5), ("hi", 0.75))}
    return {**q, "n": n, "scope": scope}


def predict_market_new(index: NewItemIndex, t: dict) -> dict | None:
    """② 시세 기준(신건판). 시세가 없거나 비교 사례가 30건 미만(시도 → 전국)이면 None."""
    mkt, app = t.get("market_price_krw"), t.get("appraisal_krw")
    if t.get("ladder_round") != 0 or not mkt or not app:
        return None
    sold = [e for e in index.window(t["category"], t["sale_date"]) if e.sold]
    for scope, pool in (
        ("시도", [e for e in sold if t.get("sido") and e.sido == t["sido"]]),
        ("전국", sold),
    ):
        if len(pool) >= MIN_POOL:
            ratios = [e.win_over_mkt for e in pool]
            q = {
                k: mkt * quantile(ratios, v) for k, v in (("lo", 0.25), ("mid", 0.5), ("hi", 0.75))
            }
            return clip_floor({**q, "n": len(pool), "scope": scope}, float(app))
    return None


def predict_band(index: NewItemIndex, t: dict) -> dict | None:
    """⑥ 감정가 ÷ 시세 구간. 구간 표본 20건 미만이면 이웃 구간과 합침, 전부 합쳐도 모자라면 None."""
    mkt, app = t.get("market_price_krw"), t.get("appraisal_krw")
    if t.get("ladder_round") != 0 or not mkt or not app:
        return None
    sold = [e for e in index.window(t["category"], t["sale_date"]) if e.sold]
    counts = [sum(1 for e in sold if e.band == b) for b in range(len(BAND_LABELS))]
    b = band_of(app / mkt)
    span = merge_bands(counts, b)
    if span is None:
        return None
    rates = [e.rate for e in sold if span[0] <= e.band <= span[1]]
    scope = (
        BAND_LABELS[b] if span == (b, b) else f"{BAND_LABELS[span[0]]}~{BAND_LABELS[span[1]]} 합침"
    )
    return clip_floor(_amounts(float(app), rates, len(rates), scope), float(app))


def mix_band_ladder(p_band: dict | None, p_ladder: dict | None) -> dict | None:
    """⑥+⑤ 섞음: 시세 있어 ⑥ 이 나오면 ⑥, 없으면 ⑤."""
    return p_band if p_band is not None else p_ladder


def p_sold_band(index: NewItemIndex, t: dict) -> float | None:
    """팔릴 확률(구간별): 같은 종류 회차 0 의 낙찰 + 유찰 중 같은 감정가 ÷ 시세 구간(20건 미만이면 이웃과 합침)의 팔린 비율."""
    mkt, app = t.get("market_price_krw"), t.get("appraisal_krw")
    if t.get("ladder_round") != 0 or not mkt or not app:
        return None
    win = index.window(t["category"], t["sale_date"])
    counts = [sum(1 for e in win if e.band == b) for b in range(len(BAND_LABELS))]
    span = merge_bands(counts, band_of(app / mkt))
    if span is None:
        return None
    pool = [e for e in win if span[0] <= e.band <= span[1]]
    return sum(1 for e in pool if e.sold) / len(pool)


def band_table(rows: list[dict]) -> list[dict]:
    """구간표(설명용, 시기를 안 가름): 감정가 ÷ 시세 구간마다 신건 건수 · 낙찰 수 · 팔린 비율 · 낙찰가율 가운데 값."""
    acc: dict[int, list[dict]] = defaultdict(list)
    for r in rows:
        if (
            r.get("ladder_round") == 0
            and r.get("market_price_krw")
            and r.get("appraisal_krw")
            and r["result"] in ("sold", "failed")
        ):
            acc[band_of(r["appraisal_krw"] / r["market_price_krw"])].append(r)
    out = []
    for b in range(len(BAND_LABELS)):
        items = acc.get(b, [])
        sold = sorted(
            float(r["sale_rate"])
            for r in items
            if r["result"] == "sold" and r.get("sale_rate") is not None
        )
        n = len(sold)
        out.append({
            "구간": BAND_LABELS[b], "신건": len(items), "낙찰": n,
            "팔린 비율 %": round(100 * n / len(items), 1) if items else None,
            "낙찰가율 가운데 값 %": round(sold[n // 2] if n % 2 else (sold[n // 2 - 1] + sold[n // 2]) / 2, 1) if n else None,
        })  # fmt: skip
    return out
