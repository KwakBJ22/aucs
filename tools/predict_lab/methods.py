"""예측 방식 셋 (순수 함수). 낙찰가는 원 단위, 비율은 감정가 대비 %로 맞춰 견준다.

① 지금 규칙: 운영과 같게 rate_range → court_cell → adjusted_rates(관할 법원 차이 · 최저가 아래 · 지난 유찰가 위로 안 감).
② 시세 기준: 낙찰가 ÷ 당시 시세의 25·50·75% × 그 달 시세. 같은 종류 · 유찰 묶음 · 시도 30건 이상, 안 되면 전국, 그래도 안 되면 뺌.
③ 머신러닝: LightGBM 분위수(10·25·50·75·90%)로 낙찰가율을 맞힘. 이길 확률 · 팔릴 확률 덤.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta

from aucs_rules.sale_rate import Sale, adjusted_rates, court_cell, fail_group, rate_range

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


# ---------- ① 지금 규칙 (운영과 같게) ----------
def rounds(r: dict) -> int | None:
    """판단에 쓰는 유찰 횟수: 최저가로 센 값(eff_failed — 우리 자료 price_round · 강사 자료는 table.pick_rounds). 없으면 법원 숫자."""
    v = r.get("eff_failed")
    return v if v is not None else r.get("failed_count")


def build_sale_pool(rows: list[dict]) -> dict[str, list[Sale]]:
    """운영 analyze.load_sales 와 같은 비교 사례(낙찰 · 낙찰가율 있음 · 지분 · 특수 · 입찰가 오기는 표를 만들 때 이미 뺌)를
    용도 이름(법원 용도 그대로)별로 묶는다. 날짜 거르기는 rate_range · court_cell 이 기준일마다 함."""
    pool: dict[str, list[Sale]] = defaultdict(list)
    for r in rows:
        if r["result"] != "sold" or r["sale_rate"] is None:
            continue
        pool[_usage_name(r)].append(
            Sale(
                sale_date=r["sale_date"],
                sido=r["sido"],
                sigungu=r.get("rate_sigungu") or r["sgg"],
                usage_name=_usage_name(r),
                area_m2=r["area_m2"],
                failed_count=rounds(r),
                sale_rate=r["sale_rate"],
                court_code=r["court_code"],
                min_rate=r["min_rate"],
            )
        )
    return pool


def _usage_name(r: dict) -> str | None:
    """운영 sale_results.usage_name 과 같은 법원 용도 이름. 없으면 종류 이름."""
    return r.get("usage_raw") or r.get("category")


def rule_values(pool: dict[str, list[Sale]], target: dict, as_of: date | None = None):
    """운영 analyze 와 똑같이: rate_range(원값) → court_cell(관할 법원 차이). 돌려주는 값: (rate 결과, court 결과)."""
    usage = _usage_name(target)
    sales = pool.get(usage, [])
    as_of = as_of or (target["sale_date"] - timedelta(days=1))
    app, mn = target["appraisal_krw"], target.get("min_price_krw")
    rates = rate_range(
        sales,
        as_of=as_of,
        sido=target["sido"],
        sigungu=target.get("rate_sigungu") or target["sgg"],
        usage_name=usage,
        area_m2=target["area_m2"],
        failed_count=rounds(target),
    )
    min_rate = round(mn * 100 / app, 1) if app and mn else None
    court = court_cell(
        sales,
        as_of=as_of,
        court_code=target["court_code"],
        usage_name=usage,
        min_rate=min_rate,
        base_p50=rates.value["p50"] if rates.value else None,
    )
    return rates, court


def predict_rule(
    train: list[dict],
    target: dict,
    pool: dict[str, list[Sale]] | None = None,
    reduction_pct: dict[str, float] | None = None,
) -> Pred | None:
    """① 지금 규칙을 운영과 같게: rate_range + court_cell + adjusted_rates(관할 법원 차이 · 최저가 아래 · 지난 유찰가 위로 안 감).
    pool(build_sale_pool)을 주면 그것을 쓰고, 없으면 train 으로 만든다. reduction_pct: 법원 코드 → 저감률 %(운영 reduction_table 과 같은 출처)."""
    pool = pool if pool is not None else build_sale_pool(train)
    rates, court = rule_values(pool, target)
    if rates.value is None:
        return None
    app, mn = target["appraisal_krw"], target.get("min_price_krw")
    red = (reduction_pct or {}).get(target["court_code"])
    adj = adjusted_rates(rates.value, court.value, app, mn, red)
    if adj is None:
        return None
    a = float(app)
    return Pred(
        p25=a * adj["lo"] / 100,
        p50=a * adj["mid"] / 100,
        p75=a * adj["hi"] / 100,
        n=rates.value["n"],
        scope=rates.value["scope"],
    )


# ---------- ② 시세 기준 ----------
def build_ratio_pools(train: list[dict]) -> dict[tuple, list[float]]:
    """(종류, 유찰 묶음, 시도) 와 (종류, 유찰 묶음, 전국) 별 「낙찰가 ÷ 당시 시세」 목록."""
    pools: dict[tuple, list[float]] = defaultdict(list)
    for r in train:
        if r["result"] != "sold" or not r["market_price_krw"] or not r["winning_bid_krw"]:
            continue
        ratio = r["winning_bid_krw"] / r["market_price_krw"]
        fg = fail_group(rounds(r))
        pools[(r["category"], fg, r["sido"])].append(ratio)
        pools[(r["category"], fg, "전국")].append(ratio)
    return pools


def predict_ratio(pools: dict[tuple, list[float]], target: dict) -> Pred | None:
    mkt = target.get("market_price_krw")
    if not mkt:
        return None
    fg = fail_group(rounds(target))
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


# ---------- 범위 폭 맞추기 (k) ----------
K_MIN_N = 30  # 지난 성적이 이보다 적으면 k 를 안 구하고 1(그대로)로 둔다
K_BOUNDS = (0.1, 10.0)


def required_k(lo: float, mid: float, hi: float, actual: float) -> float:
    """이 물건이 범위 안에 들려면 필요한 최소 배수 k (p50 중심으로 아래 폭 · 위 폭을 k 배)."""
    if actual >= mid:
        return 0.0 if actual == mid else ((actual - mid) / (hi - mid) if hi > mid else float("inf"))
    return (mid - actual) / (mid - lo) if mid > lo else float("inf")


def fit_k(history: list[dict], min_n: int = K_MIN_N) -> float | None:
    """지난 성적(history: lo · mid · hi · actual)으로 범위 안이 50%가 되는 배수: 필요한 k 들의 가운데 값.
    건수가 모자라면 None(맞추지 않음). 미래 값은 호출하는 쪽이 넣지 않는다."""
    if len(history) < min_n:
        return None
    ks = sorted(required_k(h["lo"], h["mid"], h["hi"], h["actual"]) for h in history)
    n = len(ks)
    k = ks[n // 2] if n % 2 else (ks[n // 2 - 1] + ks[n // 2]) / 2
    if k == float("inf"):
        return K_BOUNDS[1]
    return min(max(k, K_BOUNDS[0]), K_BOUNDS[1])


def apply_k(
    lo: float, mid: float, hi: float, k: float, floor: float | None = None
) -> tuple[float, float]:
    """p50 중심으로 폭을 k 배. 최저가 밑으로는 안 내려감."""
    nlo, nhi = mid - k * (mid - lo), mid + k * (hi - mid)
    if floor:
        nlo = max(nlo, float(floor))
    return nlo, nhi
