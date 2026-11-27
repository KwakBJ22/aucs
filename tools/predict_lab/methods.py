"""예측 방식 셋 (순수 함수). 낙찰가는 원 단위, 비율은 감정가 대비 %로 맞춰 견준다.

① 지금 규칙: aucs_rules.sale_rate.rate_range 를 그대로 부른다(같은 시군구 · 용도 · 면적대 · 유찰 묶음, 12개월, 10건 미만이면 넓힘).
② 시세 기준: 낙찰가 ÷ 당시 시세의 25·50·75% × 그 달 시세. 같은 종류 · 유찰 묶음 · 시도 30건 이상, 안 되면 전국, 그래도 안 되면 뺌.
③ 머신러닝: LightGBM 분위수(10·25·50·75·90%)로 낙찰가율을 맞힘. 이길 확률 · 팔릴 확률 덤.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta

from aucs_rules.sale_rate import Sale, fail_group, rate_range

RATIO_MIN_N = 30  # ② 비교 사례 최소 건수
THIN_CLASS_N = 300  # ③ 배움 자료가 이보다 적은 종류는 머신러닝에서 뺌
QS = (0.10, 0.25, 0.50, 0.75, 0.90)


@dataclass(frozen=True)
class Pred:
    p25: float  # 원
    p50: float
    p75: float
    n: int
    scope: str = ""


def quantile(xs: list[float], q: float) -> float:
    """정렬 후 선형 보간(aucs_rules.sale_rate 와 같은 방식)."""
    s = sorted(xs)
    pos = (len(s) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)


def _clip_min(v: float, min_price: int | None) -> float:
    return max(v, float(min_price)) if min_price else v


# ---------- ① 지금 규칙 ----------
def predict_rule(train: list[dict], target: dict, pool: dict | None = None) -> Pred | None:
    """train: 학습 행 목록(기준일 이전 자료). pool 을 주면 용도별로 미리 묶은 표를 씀(속도)."""
    usage = target["category"]
    source = (pool or {}).get(usage) if pool is not None else train
    if source is None:
        source = []
    since = target["sale_date"] - timedelta(days=366)
    sales = [
        Sale(
            sale_date=r["sale_date"],
            sido=r["sido"],
            sigungu=r["sgg"],
            usage_name=r["category"],
            area_m2=r["area_m2"],
            failed_count=r["failed_count"],
            sale_rate=r["sale_rate"],
            min_rate=r["min_rate"],
        )
        for r in source
        if r["sale_date"] >= since and r["result"] == "sold" and r["sale_rate"] is not None
    ]
    res = rate_range(
        sales,
        as_of=target["sale_date"] - timedelta(days=1),
        sido=target["sido"],
        sigungu=target["sgg"],
        usage_name=usage,
        area_m2=target["area_m2"],
        failed_count=target["failed_count"],
    )
    v = res.value
    if v is None:
        return None
    app = float(target["appraisal_krw"])
    mp = target.get("min_price_krw")
    return Pred(
        p25=_clip_min(app * v["p25"] / 100, mp),
        p50=_clip_min(app * v["p50"] / 100, mp),
        p75=_clip_min(app * v["p75"] / 100, mp),
        n=v["n"],
        scope=v["scope"],
    )


# ---------- ② 시세 기준 ----------
def build_ratio_pools(train: list[dict]) -> dict[tuple, list[float]]:
    """(종류, 유찰 묶음, 시도) 와 (종류, 유찰 묶음, 전국) 별 「낙찰가 ÷ 당시 시세」 목록."""
    pools: dict[tuple, list[float]] = defaultdict(list)
    for r in train:
        if r["result"] != "sold" or not r["market_price_krw"] or not r["winning_bid_krw"]:
            continue
        ratio = r["winning_bid_krw"] / r["market_price_krw"]
        fg = fail_group(r["failed_count"])
        pools[(r["category"], fg, r["sido"])].append(ratio)
        pools[(r["category"], fg, "전국")].append(ratio)
    return pools


def predict_ratio(pools: dict[tuple, list[float]], target: dict) -> Pred | None:
    mkt = target.get("market_price_krw")
    if not mkt:
        return None
    fg = fail_group(target["failed_count"])
    for key in ((target["category"], fg, target["sido"]), (target["category"], fg, "전국")):
        xs = pools.get(key, [])
        if len(xs) >= RATIO_MIN_N:
            mp = target.get("min_price_krw")
            return Pred(
                p25=_clip_min(quantile(xs, 0.25) * mkt, mp),
                p50=_clip_min(quantile(xs, 0.50) * mkt, mp),
                p75=_clip_min(quantile(xs, 0.75) * mkt, mp),
                n=len(xs),
                scope=key[2],
            )
    return None


# ---------- 확률 보조 ----------
def cdf_from_quantiles(x: float, q_vals: list[float]) -> float:
    """분위수(10·25·50·75·90% 지점의 낙찰가율, %) → P(낙찰가율 ≤ x). 양 끝은 선형으로 이어 0 · 1 까지."""
    p10, p25, p50, p75, p90 = q_vals
    if x <= p10:
        span = max(2 * (p25 - p10), 1e-9)
        return max(0.0, 0.10 * (x - (p10 - span)) / span)
    if x >= p90:
        span = max(2 * (p90 - p75), 1e-9)
        return min(1.0, 0.90 + 0.10 * min(1.0, (x - p90) / span))
    knots = [(p10, 0.10), (p25, 0.25), (p50, 0.50), (p75, 0.75), (p90, 0.90)]
    for (xa, pa), (xb, pb) in zip(knots, knots[1:], strict=False):
        if xa <= x <= xb:
            if xb == xa:
                return pb
            return pa + (pb - pa) * (x - xa) / (xb - xa)
    return 0.5


def brier(p: list[float], y: list[int]) -> float:
    return sum((a - b) ** 2 for a, b in zip(p, y, strict=True)) / len(p) if p else float("nan")


def calibration(pairs: list[tuple[float, int]], bins: int = 10) -> list[dict]:
    """예측 확률을 10% 칸으로 나눠 예측 평균 · 실제 비율을 본다."""
    out = []
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        items = [(p, y) for p, y in pairs if lo <= p < hi or (b == bins - 1 and p == 1.0)]
        if not items:
            out.append(
                {
                    "칸": f"{int(lo * 100)}~{int(hi * 100)}%",
                    "건수": 0,
                    "예측 평균": None,
                    "실제 비율": None,
                }
            )
            continue
        out.append(
            {
                "칸": f"{int(lo * 100)}~{int(hi * 100)}%",
                "건수": len(items),
                "예측 평균": round(sum(p for p, _ in items) / len(items), 3),
                "실제 비율": round(sum(y for _, y in items) / len(items), 3),
            }
        )
    return out


def months_range(start: date, end: date) -> list[date]:
    """start~end 사이 각 달의 1일 목록."""
    out, y, m = [], start.year, start.month
    while date(y, m, 1) <= end:
        out.append(date(y, m, 1))
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out
