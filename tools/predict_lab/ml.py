"""③ 머신러닝: LightGBM 분위수(낙찰가율) + 팔릴 확률 분류. 입력은 학습 행 목록(순수 자료 · 기준일 이전만)."""

from __future__ import annotations

import numpy as np
import pandas as pd
from methods import QS

FEATURES = [
    "category", "sido", "court", "failed_count", "log_app", "min_rate", "market_ratio",
    "area_m2", "month", "signal_count", "high_count", "tenant_count",
]  # fmt: skip
FEATURE_KO = {
    "category": "종류", "sido": "시도", "court": "법원", "failed_count": "유찰 횟수",
    "log_app": "감정가(로그)", "min_rate": "최저가율", "market_ratio": "시세÷감정가",
    "area_m2": "전용면적", "month": "매각 월", "signal_count": "위험 신호 수(우리 자료)",
    "high_count": "높은 위험 신호 수(우리 자료)", "tenant_count": "임차인 수(우리 자료)",
}  # fmt: skip


def _levels(rows: list[dict]) -> dict[str, list]:
    return {
        "category": sorted({r["category"] for r in rows if r["category"]}),
        "sido": sorted({str(r["sido"]) for r in rows if r["sido"]}),
        "court": sorted({str(r["court_code"]) for r in rows if r["court_code"]}),
    }


def frame(rows: list[dict], levels: dict[str, list]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    num = lambda c: pd.to_numeric(df[c], errors="coerce").astype(float)  # noqa: E731
    out = pd.DataFrame(index=df.index)
    out["category"] = pd.Categorical(df["category"], categories=levels["category"])
    out["sido"] = pd.Categorical(df["sido"].astype(object), categories=levels["sido"])
    out["court"] = pd.Categorical(df["court_code"].astype(object), categories=levels["court"])
    out["failed_count"] = (
        num("eff_failed").fillna(num("failed_count")) if "eff_failed" in df else num("failed_count")
    )
    out["log_app"] = np.log(num("appraisal_krw"))
    out["min_rate"] = num("min_rate")
    out["market_ratio"] = num("market_ratio")
    out["area_m2"] = num("area_m2")
    out["month"] = df["sale_date"].map(lambda d: d.month).astype(float)
    out["signal_count"] = num("signal_count")
    out["high_count"] = num("high_count")
    out["tenant_count"] = num("tenant_count")
    return out[FEATURES]


def fit(train: list[dict], seed: int = 7, n_estimators: int = 300) -> dict:
    import lightgbm as lgb

    levels = _levels(train)
    sold = [r for r in train if r["result"] == "sold" and r["sale_rate"] is not None]
    X = frame(sold, levels)
    y = np.array([float(r["sale_rate"]) for r in sold])
    params = dict(
        learning_rate=0.05, num_leaves=31, min_child_samples=20, random_state=seed, verbose=-1
    )
    quantile_models = {
        q: lgb.LGBMRegressor(
            objective="quantile", alpha=q, n_estimators=n_estimators, **params
        ).fit(X, y)
        for q in QS
    }
    Xa = frame(train, levels)
    ya = np.array([1 if r["result"] == "sold" else 0 for r in train])
    clf = lgb.LGBMClassifier(n_estimators=n_estimators, **params).fit(Xa, ya)
    thin_counts: dict[str, int] = {}
    for r in sold:
        thin_counts[r["category"]] = thin_counts.get(r["category"], 0) + 1
    return {"levels": levels, "q": quantile_models, "clf": clf, "sold_by_category": thin_counts}


def predict(model: dict, rows: list[dict]) -> list[dict]:
    """각 행: 낙찰가율 분위수(%, 오름차순 정렬) · 팔릴 확률."""
    if not rows:
        return []
    X = frame(rows, model["levels"])
    qs = np.column_stack([model["q"][q].predict(X) for q in QS])
    qs.sort(axis=1)  # 분위수 교차 방지
    p_sold = model["clf"].predict_proba(X)[:, 1]
    return [
        {"ratio_q": [float(v) for v in qs[i]], "p_sold": float(p_sold[i])} for i in range(len(rows))
    ]


def importance(model: dict, top: int = 15) -> list[dict]:
    """중앙값 모형이 크게 본 칸 순위(gain 기준, 비율)."""
    booster = model["q"][0.50].booster_
    gains = booster.feature_importance(importance_type="gain")
    total = float(gains.sum()) or 1.0
    names = booster.feature_name()
    rows = sorted(zip(names, gains, strict=True), key=lambda t: -t[1])[:top]
    return [{"칸": FEATURE_KO.get(n, n), "비중(%)": round(100 * g / total, 1)} for n, g in rows]
