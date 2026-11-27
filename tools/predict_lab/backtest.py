"""되짚어 채점: 달마다 「그달 전까지 자료로 배우고 그달을 맞힘」. 방식 ①·②·③을 같은 물건으로 견준다.

실행(저장소 맨 위에서): uv run --no-project --with lightgbm --with pandas --with pyarrow --with-editable packages/rules python tools/predict_lab/backtest.py
결과: data\\predict_lab\\report_YYYYMMDD.md · report_YYYYMMDD.json
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

from methods import (
    THIN_CLASS_N,
    brier,
    build_ratio_pools,
    calibration,
    cdf_from_quantiles,
    months_range,
    predict_ratio,
    predict_rule,
)
from paths import LAB_DIR
from usage import CLASSES

METHODS = ("①지금 규칙", "②시세 기준", "③머신러닝")
CATS = list(CLASSES)
BID_GRID = list(range(40, 125, 5))  # 이길 확률 점검: 입찰가율 40~120% (5%p 간격)


def load_rows(table: Path) -> list[dict]:
    import pandas as pd

    df = pd.read_parquet(table)
    df = df.astype(object).where(pd.notna(df), None)
    return df.to_dict("records")


def next_month(d: date) -> date:
    return date(d.year + (d.month == 12), d.month % 12 + 1, 1)


def _err_metrics(items: list[dict]) -> dict:
    """채점 행(낙찰 건) 목록 → 성적. items: {lo, mid, hi, actual, appraisal, pred_mid_ratio, actual_ratio}."""
    n = len(items)
    if n == 0:
        return {"건수": 0}
    inside = sum(1 for i in items if i["lo"] <= i["actual"] <= i["hi"])
    low = sum(1 for i in items if i["actual"] < i["lo"])
    high = sum(1 for i in items if i["actual"] > i["hi"])
    mid_err = sum(abs(i["actual"] - i["mid"]) / i["actual"] for i in items if i["actual"]) / n
    wrong10 = sum(1 for i in items if abs(i["pred_mid_ratio"] - i["actual_ratio"]) > 10) / n
    return {
        "건수": n,
        "범위 안(25~75%) %": round(100 * inside / n, 1),
        "낮게 %": round(100 * low / n, 1),
        "높게 %": round(100 * high / n, 1),
        "가운데 오차 %": round(100 * mid_err, 1),
        "10%p 넘게 틀린 %": round(100 * wrong10, 1),
    }


def run(table: Path, out_dir: Path, today: date) -> dict:
    rows = load_rows(table)
    rows.sort(key=lambda r: (r["sale_date"], r["court_code"], str(r["case_no"]), r["item_no"] or 0))
    first = min(r["sale_date"] for r in rows).replace(day=1)
    last = max(r["sale_date"] for r in rows)
    months = months_range(first, last)

    # 방식별 채점 행: (method, category, month) → 낙찰 건 목록; 제외 건수
    scored: dict[tuple, list[dict]] = defaultdict(list)
    excluded: Counter = Counter()
    common: dict[str, list[dict]] = defaultdict(list)  # 세 방식이 다 낸 물건
    bid_pairs: list[tuple[float, int]] = []
    sold_pairs: list[tuple[float, int]] = []
    importance_last: list[dict] = []
    monthly_meta: list[dict] = []

    import ml  # LightGBM 은 무거워서 필요할 때만

    for m in months[1:]:  # 첫 달은 배움용으로만
        nxt = next_month(m)
        train = [r for r in rows if r["sale_date"] < m]
        test = [r for r in rows if m <= r["sale_date"] < nxt]
        if not test:
            continue
        model = ml.fit(train)
        thin = {c for c, n in model["sold_by_category"].items() if n < THIN_CLASS_N}
        ml_pred = ml.predict(model, test)
        pools = build_ratio_pools(train)
        by_usage: dict[str, list[dict]] = defaultdict(list)
        for r in train:
            if r["result"] == "sold":
                by_usage[r["category"]].append(r)

        for t, mp in zip(test, ml_pred, strict=True):
            cat = t["category"]
            if t["result"] != "sold":
                # 유찰: 가격은 채점 안 함. 팔릴 확률만 채점
                sold_pairs.append((mp["p_sold"], 0))
                continue
            actual = float(t["winning_bid_krw"])
            app = float(t["appraisal_krw"])
            actual_ratio = actual * 100 / app
            sold_pairs.append((mp["p_sold"], 1))
            for x in BID_GRID:
                bid_pairs.append(
                    (cdf_from_quantiles(x, mp["ratio_q"]), 1 if actual_ratio <= x else 0)
                )

            preds: dict[str, dict | None] = {}
            p1 = predict_rule(train, t, pool=by_usage)
            p2 = predict_ratio(pools, t)
            preds[METHODS[0]] = _as_dict(p1)
            preds[METHODS[1]] = _as_dict(p2)
            if cat in thin or cat not in CATS:
                preds[METHODS[2]] = None
                excluded[(METHODS[2], cat)] += 1
            else:
                ratio_q = mp["ratio_q"]
                preds[METHODS[2]] = {
                    "lo": app * ratio_q[1] / 100, "mid": app * ratio_q[2] / 100, "hi": app * ratio_q[3] / 100,
                    "n": model["sold_by_category"].get(cat, 0), "scope": "ML",
                }  # fmt: skip
                mn = t.get("min_price_krw")
                if mn:
                    for k in ("lo", "mid", "hi"):
                        preds[METHODS[2]][k] = max(preds[METHODS[2]][k], float(mn))

            for meth, p in preds.items():
                if p is None:
                    excluded[(meth, cat)] += 1
                    continue
                item = {
                    "lo": p["lo"], "mid": p["mid"], "hi": p["hi"], "actual": actual,
                    "pred_mid_ratio": p["mid"] * 100 / app, "actual_ratio": actual_ratio,
                }  # fmt: skip
                scored[(meth, cat, m.isoformat()[:7])].append(item)
                scored[(meth, "전체", m.isoformat()[:7])].append(item)
            if all(preds[k] is not None for k in METHODS):
                for meth in METHODS:
                    p = preds[meth]
                    common[cat].append({
                        "method": meth, "lo": p["lo"], "mid": p["mid"], "hi": p["hi"], "actual": actual,
                        "pred_mid_ratio": p["mid"] * 100 / app, "actual_ratio": actual_ratio,
                        "item": f"{t['court_code']}|{t['case_no']}|{t['item_no']}|{t['sale_date']}",
                    })  # fmt: skip

        monthly_meta.append({
            "month": m.isoformat()[:7], "train_rows": len(train), "test_rows": len(test),
            "test_sold": sum(1 for t in test if t["result"] == "sold"),
            "sold_by_category_train": model["sold_by_category"], "thin": sorted(thin),
        })  # fmt: skip
        importance_last = ml.importance(model)

    # --- 요약 ---
    per_cell = {}
    for (meth, cat, mon), items in scored.items():
        per_cell.setdefault(cat, {}).setdefault(meth, {})[mon] = _err_metrics(items)
    pooled = {}
    for (meth, cat, _), items in scored.items():
        pooled.setdefault(cat, {}).setdefault(meth, []).extend(items)
    pooled_metrics = {c: {m: _err_metrics(v) for m, v in d.items()} for c, d in pooled.items()}

    winners = {}
    for cat in CATS:
        by_item = defaultdict(dict)
        for it in common.get(cat, []):
            by_item[it["item"]][it["method"]] = it
        full = [v for v in by_item.values() if len(v) == 3]
        if len(full) < 30:
            winners[cat] = {"이긴 방식": "표본 적음", "건수": len(full)}
            continue
        err = {
            m: sum(abs(v[m]["actual"] - v[m]["mid"]) / v[m]["actual"] for v in full) / len(full)
            for m in METHODS
        }
        inside = {
            m: sum(1 for v in full if v[m]["lo"] <= v[m]["actual"] <= v[m]["hi"]) / len(full)
            for m in METHODS
        }
        best = min(err, key=err.get)
        winners[cat] = {
            "이긴 방식": best,
            "건수": len(full),
            "가운데 오차 %": {m: round(100 * e, 1) for m, e in err.items()},
            "범위 안 %": {m: round(100 * c, 1) for m, c in inside.items()},
        }

    sold_p = [p for p, y in sold_pairs]
    sold_y = [y for p, y in sold_pairs]
    result = {
        "built_on": today.isoformat(),
        "eval_months": [m["month"] for m in monthly_meta],
        "monthly": monthly_meta,
        "winners": winners,
        "pooled": pooled_metrics,
        "per_month": per_cell,
        "excluded": {f"{m}|{c}": n for (m, c), n in excluded.items()},
        "bid_calibration": calibration(bid_pairs),
        "sold_brier": round(brier(sold_p, sold_y), 4) if sold_p else None,
        "sold_calibration": calibration(sold_pairs),
        "importance_last_month": importance_last,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"report_{today:%Y%m%d}.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    (out_dir / f"report_{today:%Y%m%d}.md").write_text(render(result, today), encoding="utf-8")
    return result


def _as_dict(p) -> dict | None:
    if p is None:
        return None
    return {"lo": p.p25, "mid": p.p50, "hi": p.p75, "n": p.n, "scope": p.scope}


def render(r: dict, today: date) -> str:
    lines = [f"# 낙찰가 예측 되짚어 채점 ({today:%Y-%m-%d})", ""]
    lines.append("## 요약 (맨 위 세 줄)")
    for cat in CATS:
        w = r["winners"].get(cat, {"이긴 방식": "표본 적음", "건수": 0})
        if w["이긴 방식"] == "표본 적음":
            lines.append(f"- {cat}: 세 방식 다 낸 물건 {w['건수']}건 — 시세가 없어 ②를 못 내서 가릴 수 없음" if w["건수"] == 0
                         else f"- {cat}: 세 방식 다 낸 물건 {w['건수']}건 — 표본 적어 가릴 수 없음")  # fmt: skip
        else:
            e = w["가운데 오차 %"]
            err = " · ".join(f"{m} {v}%" for m, v in e.items())
            ins = " · ".join(f"{m} {v}%" for m, v in w["범위 안 %"].items())
            lines.append(
                f"- {cat}: 이긴 방식 **{w['이긴 방식']}** · 세 방식 다 낸 {w['건수']}건 기준 "
                f"(가운데 오차 {err} / 범위 안 {ins})"
            )
    lines += ["", f"평가 달: {', '.join(r['eval_months']) or '없음'} (첫 달은 배움용)", ""]

    lines.append("## 종류별 성적 (전체 달 합산)")
    lines.append(
        "| 종류 | 방식 | 건수 | 범위 안 % | 낮게 % | 높게 % | 가운데 오차 % | 10%p 넘게 틀린 % |"
    )
    lines.append("|---|---|---|---|---|---|---|---|")
    for cat in ["전체", *CATS]:
        for meth in METHODS:
            m = r["pooled"].get(cat, {}).get(meth)
            if not m or m.get("건수", 0) == 0:
                lines.append(f"| {cat} | {meth} | 0 | - | - | - | - | - |")
                continue
            lines.append(
                f"| {cat} | {meth} | {m['건수']} | {m['범위 안(25~75%) %']} | {m['낮게 %']} | {m['높게 %']} | {m['가운데 오차 %']} | {m['10%p 넘게 틀린 %']} |"
            )
    lines.append("")
    lines.append("## 달마다 성적 (전체 종류)")
    lines.append("| 달 | 방식 | 건수 | 범위 안 % | 가운데 오차 % | 10%p 넘게 틀린 % |")
    lines.append("|---|---|---|---|---|---|")
    for mon in r["eval_months"]:
        for meth in METHODS:
            m = r["per_month"].get("전체", {}).get(meth, {}).get(mon)
            if m and m.get("건수"):
                lines.append(
                    f"| {mon} | {meth} | {m['건수']} | {m['범위 안(25~75%) %']} | {m['가운데 오차 %']} | {m['10%p 넘게 틀린 %']} |"
                )
    lines.append("")
    lines.append("## 제외 건수 (방식별 · 종류별, 낙찰 건 기준)")
    for k, n in sorted(r["excluded"].items()):
        lines.append(f"- {k}: {n}건")
    lines.append("")
    lines.append("## 이길 확률 점검 (입찰가율 X% 로 쓰면 이길 확률, 10% 칸)")
    lines.append("| 예측 칸 | 건수 | 예측 평균 | 실제 비율 |")
    lines.append("|---|---|---|---|")
    for row in r["bid_calibration"]:
        lines.append(f"| {row['칸']} | {row['건수']} | {row['예측 평균']} | {row['실제 비율']} |")
    lines.append("")
    lines.append(f"## 이번 회차에 팔릴 확률 (Brier 점수 {r['sold_brier']})")
    lines.append("| 예측 칸 | 건수 | 예측 평균 | 실제 비율 |")
    lines.append("|---|---|---|---|")
    for row in r["sold_calibration"]:
        lines.append(f"| {row['칸']} | {row['건수']} | {row['예측 평균']} | {row['실제 비율']} |")
    lines.append("")
    lines.append("## 머신러닝이 크게 본 칸 (마지막 달 모형, 상위 15)")
    for row in r["importance_last_month"]:
        lines.append(f"- {row['칸']}: {row['비중(%)']}%")
    lines.append("")
    lines.append("## 학습 자료")
    for mm in r["monthly"]:
        lines.append(
            f"- {mm['month']}: 배움 {mm['train_rows']}건 → 맞힘 {mm['test_rows']}건(낙찰 {mm['test_sold']}) · 배움 낙찰 종류별 {mm['sold_by_category_train']}"
        )
    lines.append("")
    lines.append(
        "주의: 시세 칸은 강사 자료에 지번이 없어 단지 이름으로 맞춘 것이 섞여 있다. 맞춘 건수는 build_table 요약(table_*_summary.json)을 본다."
    )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    tables = sorted(LAB_DIR.glob("table_????????.parquet"))
    if not tables:
        sys.exit("학습 표가 없습니다. 먼저 build_table.py 를 실행하세요.")
    latest = tables[-1]
    today = date.today()
    res = run(latest, LAB_DIR, today)
    print(render(res, today))
