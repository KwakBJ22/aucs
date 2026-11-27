"""되짚어 채점: 달마다 「그달 전까지 자료로 배우고 그달을 맞힘」. 방식 ①·②·③을 같은 물건으로 견준다.

- ① 지금 규칙은 운영과 같은 길(rate_range → court_cell → adjusted_rates)로, 물건마다 그 매각일 전 낙찰만 쓴다.
- 먼저 「맞춰 보기」: 입찰 전 분석 스냅샷(analysis.sale_snapshots)의 낙찰가율 p25 · p50 · p75 와 ① 이 같은지.
- 시세는 두 가지로 돌린다: 「전체(d 포함)」 = 지번 (a)(b)(c) + 단지 이름 (d), 「지번만」 = (a)(b)(c).
- 범위 폭 맞추기: 방식 · 종류마다 지난달까지 성적으로 배수 k 를 정해(범위 안 50%) 그달에 적용. 미래 달은 안 봄.

실행(저장소 맨 위에서): uv run --no-project --with lightgbm --with scikit-learn --with pandas --with pyarrow --with-editable packages/rules python tools/predict_lab/backtest.py
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
    apply_k,
    brier,
    build_ratio_pools,
    build_sale_pool,
    calibration,
    cdf_from_quantiles,
    fit_k,
    months_range,
    predict_ratio,
    predict_rule,
    rule_values,
)
from paths import LAB_DIR, REDUCTION_JSON
from usage import CLASSES

METHODS = ("①지금 규칙", "②시세 기준", "③머신러닝")
CATS = list(CLASSES)
MARKET_CATS = ("아파트", "빌라", "오피스텔")  # 시세를 붙이는 종류 — ② 는 여기서만 냄
BID_GRID = list(range(40, 125, 5))  # 이길 확률 점검: 입찰가율 40~120% (5%p 간격)
VARIANTS = {"all": "전체(지번 a·b·c + 단지 이름 d)", "strict": "지번만(a·b·c)"}
MARKET_COLS = (
    "market_price_krw", "market_level", "market_n", "market_ratio",
    "appraisal_over_market", "win_over_market",
)  # fmt: skip


def load_rows(table: Path) -> list[dict]:
    import pandas as pd

    df = pd.read_parquet(table)
    df = df.astype(object).where(pd.notna(df), None)
    return df.to_dict("records")


def read_reduction_pct(path: Path = REDUCTION_JSON) -> dict[str, float]:
    """운영 picks.reduction_table 과 같은 출처(기준표 court_reduction_pct 중 verified 인 법원)."""
    if not path.exists():
        return {}
    d = json.loads(path.read_text(encoding="utf-8"))
    ok = set(d.get("verified", []))
    return {c: v for c, v in d.get("pct", {}).items() if c in ok}


def variant_rows(rows: list[dict], variant: str) -> list[dict]:
    """strict: 단지 이름(d)으로만 붙은 시세는 비움(복사본). all: 그대로."""
    if variant == "all":
        return rows
    out = []
    for r in rows:
        if r.get("market_how") == "name":
            r = dict(r)
            for c in MARKET_COLS:
                r[c] = None
            r["market_how"] = None
        out.append(r)
    return out


def next_month(d: date) -> date:
    return date(d.year + (d.month == 12), d.month % 12 + 1, 1)


# ---------- 맞춰 보기: ① 과 입찰 전 분석 스냅샷 ----------
# 운영 ① 이 지금 규칙과 같아진 날: 유찰 횟수를 최저가로 셈(price_round, rules-0.20.0) — 그 전 스냅샷은
# 다른 규칙(법원 유찰 숫자 · 입찰가 오기 안 뺌 등)으로 만든 것이라 맞춰 보기 기준에서 따로 본다(11/27).
NOW_RULES_FROM = date(2026, 11, 24)
NOW_ENGINE = (
    0,
    20,
    0,
)  # 스냅샷의 engine_version 이 이 이상이면 지금 규칙(rules-0.20.0 · price_round)으로 만든 것


def _engine_tuple(v: str | None) -> tuple[int, ...] | None:
    try:
        return tuple(int(x) for x in str(v).split("-", 1)[1].split("."))
    except (IndexError, ValueError):
        return None


def parity_check(
    rows: list[dict], since: date | None = None, engine_from: tuple | None = None
) -> dict:
    """스냅샷 낙찰(학습 표에 있는 것)마다 ① 의 낙찰가율 p25·p50·p75(원값, 법원 차이 · 최저가 손질 전)를 스냅샷의
    analysis->sale_rate 와 견준다. 기준일은 스냅샷을 만든 날. 비교 사례 묶음 두 가지: 실험실 전체 · 우리 낙찰만(운영과 같은 자료)."""
    snaps = [
        r for r in rows
        if r["result"] == "sold" and r.get("snap_p50") is not None and r.get("snap_date") is not None
        and (since is None or r["snap_date"] >= since)
        and (engine_from is None or ((_engine_tuple(r.get("snap_engine")) or (0,)) >= engine_from))
    ]  # fmt: skip  # 비교 사례(pool)는 언제나 표 전체 — since 는 견줄 스냅샷만 고름
    if not snaps:
        return {"건수": 0}
    pools = {
        "실험실 전체 자료": build_sale_pool(rows),
        "우리 낙찰만(운영과 같은 자료)": build_sale_pool([r for r in rows if r["src"] == "ours"]),
    }
    out: dict = {
        "건수": len(snaps),
        "스냅샷 날짜": [
            str(min(r["snap_date"] for r in snaps)),
            str(max(r["snap_date"] for r in snaps)),
        ],
    }
    detail = []
    for name, pool in pools.items():
        within = {"p25": 0, "p50": 0, "p75": 0}
        none = n_same = 0
        diffs = []
        by_cat: dict[str, list[int]] = defaultdict(lambda: [0, 0])
        for r in snaps:
            rates, _ = rule_values(pool, r, as_of=r["snap_date"])
            v = rates.value
            c = by_cat[r["category"]]
            c[1] += 1
            if v is None:
                none += 1
                continue
            for key in within:
                within[key] += abs(v[key] - r[f"snap_{key}"]) <= 1.0 + 1e-9
            c[0] += abs(v["p50"] - r["snap_p50"]) <= 1.0 + 1e-9
            n_same += v["n"] == r["snap_n"]
            diffs.append(abs(v["p50"] - r["snap_p50"]))
            detail.append((name, r, v))
        n = len(snaps)
        diffs.sort()
        out[name] = {
            "p50 차이 1%p 안 %": round(100 * within["p50"] / n, 1),
            "p25 차이 1%p 안 %": round(100 * within["p25"] / n, 1),
            "p75 차이 1%p 안 %": round(100 * within["p75"] / n, 1),
            "표본 수(n)가 같은 %": round(100 * n_same / n, 1),
            "p50 차이 가운데 값(%p)": round(diffs[len(diffs) // 2], 2) if diffs else None,
            "① 이 못 낸 건수": none,
            "종류별 p50 1%p 안 %": {
                c: f"{round(100 * a / b, 1)} ({b}건)" for c, (a, b) in sorted(by_cat.items())
            },
        }
    return out


# ---------- 채점 ----------
def _in(i: dict, lo_key: str = "lo", hi_key: str = "hi") -> bool:
    return i[lo_key] <= i["actual"] <= i[hi_key]


def _err_metrics(items: list[dict]) -> dict:
    """채점 행(낙찰 건) 목록 → 성적. 맞춘 뒤 범위 안은 k 를 구할 수 있었던 달의 물건만(건수 따로)."""
    n = len(items)
    if n == 0:
        return {"건수": 0}
    inside = sum(1 for i in items if _in(i))
    low = sum(1 for i in items if i["actual"] < i["lo"])
    high = sum(1 for i in items if i["actual"] > i["hi"])
    mid_err = sum(abs(i["actual"] - i["mid"]) / i["actual"] for i in items if i["actual"]) / n
    wrong10 = sum(1 for i in items if abs(i["pred_mid_ratio"] - i["actual_ratio"]) > 10) / n
    adj = [i for i in items if i.get("lo_adj") is not None]
    out = {
        "건수": n,
        "범위 안(25~75%) %": round(100 * inside / n, 1),
        "낮게 %": round(100 * low / n, 1),
        "높게 %": round(100 * high / n, 1),
        "가운데 오차 %": round(100 * mid_err, 1),
        "10%p 넘게 틀린 %": round(100 * wrong10, 1),
        "맞춘 건수": len(adj),
    }
    if adj:
        out["그 물건들 원래 범위 안 %"] = round(100 * sum(1 for i in adj if _in(i)) / len(adj), 1)
        out["그 물건들 맞춘 뒤 범위 안 %"] = round(
            100 * sum(1 for i in adj if _in(i, "lo_adj", "hi_adj")) / len(adj), 1
        )
    return out


def assign_month_k(
    month_recs: list[dict],
    history: dict[tuple, list[dict]],
    k_table: dict[str, dict],
    mon: str,
) -> None:
    """이 달 채점 행에 범위 폭 배수 k 를 붙인다. k 는 방식 · 종류마다 history(지난 달들)만으로 정함 — month_recs 자신은 안 봄."""
    ks: dict[tuple, float | None] = {}
    for meth in METHODS:
        for cat in CATS:
            ks[(meth, cat)] = fit_k(history[(meth, cat)])
            k_table[f"{meth}|{cat}"][mon] = (
                None if ks[(meth, cat)] is None else round(ks[(meth, cat)], 2)
            )
    for rec in month_recs:
        k = ks.get((rec["method"], rec["cat"]))
        if k is not None:
            rec["k"] = k
            rec["lo_adj"], rec["hi_adj"] = apply_k(
                rec["lo"], rec["mid"], rec["hi"], k, rec["floor"]
            )


def evaluate(rows: list[dict], months: list[date], pool: dict, reduction: dict[str, float]) -> dict:
    """한 시세 묶음(variant)의 되짚어 채점. 달마다: 그 달 전 낙찰로 ②③ 을 배우고, ① 은 물건마다 매각일 전 낙찰로 셈."""
    records: list[dict] = []  # 낙찰 건 × 방식
    excluded: Counter = Counter()
    bid_pairs: list[tuple[float, int]] = []
    sold_pairs: list[tuple[float, int]] = []
    importance_last: list[dict] = []
    monthly_meta: list[dict] = []
    history: dict[tuple, list[dict]] = defaultdict(list)  # (방식, 종류) → 지난 달들의 채점 행
    k_table: dict[str, dict] = defaultdict(dict)  # "방식|종류" → {달: k}

    import ml  # LightGBM 은 무거워서 필요할 때만

    for m in months[1:]:  # 첫 달은 배움용으로만
        nxt = next_month(m)
        train = [r for r in rows if r["sale_date"] < m]
        test = [r for r in rows if m <= r["sale_date"] < nxt]
        if not test:
            continue
        mon = m.isoformat()[:7]
        model = ml.fit(train)
        thin = {c for c, n in model["sold_by_category"].items() if n < THIN_CLASS_N}
        ml_pred = ml.predict(model, test)
        pools = build_ratio_pools(train)
        month_recs: list[dict] = []

        for t, mp in zip(test, ml_pred, strict=True):
            cat = t["category"]
            if t["result"] != "sold":
                sold_pairs.append((mp["p_sold"], 0))  # 유찰: 가격은 채점 안 함. 팔릴 확률만
                continue
            actual = float(t["winning_bid_krw"])
            app = float(t["appraisal_krw"])
            actual_ratio = actual * 100 / app
            sold_pairs.append((mp["p_sold"], 1))
            for x in BID_GRID:
                bid_pairs.append(
                    (cdf_from_quantiles(x, mp["ratio_q"]), 1 if actual_ratio <= x else 0)
                )

            preds: dict[str, dict | None] = {
                METHODS[0]: _as_dict(predict_rule([], t, pool=pool, reduction_pct=reduction)),
                METHODS[1]: _as_dict(predict_ratio(pools, t)),
            }
            if cat in thin or cat not in CATS:
                preds[METHODS[2]] = None
            else:
                q = mp["ratio_q"]
                preds[METHODS[2]] = {
                    "lo": app * q[1] / 100, "mid": app * q[2] / 100, "hi": app * q[3] / 100,
                    "n": model["sold_by_category"].get(cat, 0), "scope": "ML",
                }  # fmt: skip
                mn = t.get("min_price_krw")
                if mn:
                    for k in ("lo", "mid", "hi"):
                        preds[METHODS[2]][k] = max(preds[METHODS[2]][k], float(mn))
            key = f"{t['court_code']}|{t['case_no']}|{t['item_no']}|{t['sale_date']}"
            for meth, p in preds.items():
                if p is None:
                    excluded[(meth, cat)] += 1
                    continue
                month_recs.append({
                    "method": meth, "cat": cat, "month": mon, "item": key,
                    "lo": p["lo"], "mid": p["mid"], "hi": p["hi"], "actual": actual,
                    "floor": t.get("min_price_krw"),
                    "pred_mid_ratio": p["mid"] * 100 / app, "actual_ratio": actual_ratio,
                    "lo_adj": None, "hi_adj": None, "k": None,
                })  # fmt: skip

        # 범위 폭 맞추기: k 는 지난 달까지의 성적(history)으로만 정한다 — 이번 달 · 미래 값은 안 봄
        assign_month_k(month_recs, history, k_table, mon)
        for rec in month_recs:  # 이 달 성적은 다음 달부터 k 에 쓴다
            history[(rec["method"], rec["cat"])].append(rec)
        records.extend(month_recs)

        monthly_meta.append({
            "month": mon, "train_rows": len(train), "test_rows": len(test),
            "test_sold": sum(1 for t in test if t["result"] == "sold"),
            "sold_by_category_train": model["sold_by_category"], "thin": sorted(thin),
        })  # fmt: skip
        importance_last = ml.importance(model)

    per_cell: dict = {}
    pooled: dict = {}
    grouped: dict[tuple, list[dict]] = defaultdict(list)
    for rec in records:
        for c in (rec["cat"], "전체"):
            grouped[(rec["method"], c, rec["month"])].append(rec)
            pooled.setdefault((c, rec["method"]), []).append(rec)
    for (meth, cat, mon), items in grouped.items():
        per_cell.setdefault(cat, {}).setdefault(meth, {})[mon] = _err_metrics(items)
    pooled_metrics: dict = {}
    for (cat, meth), items in pooled.items():
        pooled_metrics.setdefault(cat, {})[meth] = _err_metrics(items)

    return {
        "monthly": monthly_meta,
        "winners": {c: winner(records, c, METHODS) for c in MARKET_CATS}
        | {c: winner(records, c, (METHODS[0], METHODS[2])) for c in CATS if c not in MARKET_CATS},
        "pooled": pooled_metrics,
        "per_month": per_cell,
        "excluded": {f"{m}|{c}": n for (m, c), n in excluded.items()},
        "k_table": dict(k_table),
        "bid_calibration": calibration(bid_pairs),
        "sold_brier": round(brier([p for p, _ in sold_pairs], [y for _, y in sold_pairs]), 4)
        if sold_pairs
        else None,
        "sold_calibration": calibration(sold_pairs),
        "importance_last_month": importance_last,
    }


def winner(records: list[dict], cat: str, methods: tuple[str, ...], min_n: int = 30) -> dict:
    """같은 물건끼리(고른 방식이 모두 낸 물건) 가운데 오차가 가장 작은 방식. 범위 안은 원래 / 맞춘 뒤 둘 다."""
    by_item: dict[str, dict[str, dict]] = defaultdict(dict)
    for rec in records:
        if rec["cat"] == cat and rec["method"] in methods:
            by_item[rec["item"]][rec["method"]] = rec
    full = [v for v in by_item.values() if len(v) == len(methods)]
    if len(full) < min_n:
        return {"이긴 방식": "표본 적음", "건수": len(full), "비교한 방식": list(methods)}
    err = {
        m: sum(abs(v[m]["actual"] - v[m]["mid"]) / v[m]["actual"] for v in full) / len(full)
        for m in methods
    }
    inside = {m: sum(1 for v in full if _in(v[m])) / len(full) for m in methods}
    adj_full = [v for v in full if all(v[m]["lo_adj"] is not None for m in methods)]
    inside_adj = {
        m: (sum(1 for v in adj_full if _in(v[m], "lo_adj", "hi_adj")) / len(adj_full))
        if adj_full
        else None
        for m in methods
    }
    inside_adj_orig = {
        m: (sum(1 for v in adj_full if _in(v[m])) / len(adj_full)) if adj_full else None
        for m in methods
    }
    best = min(err, key=err.get)
    pct = lambda d: {m: (None if v is None else round(100 * v, 1)) for m, v in d.items()}  # noqa: E731
    return {
        "이긴 방식": best,
        "비교한 방식": list(methods),
        "건수": len(full),
        "가운데 오차 %": pct(err),
        "범위 안(원래) %": pct(inside),
        "맞춘 뒤 비교 건수": len(adj_full),
        "그 건수의 범위 안(원래) %": pct(inside_adj_orig),
        "범위 안(맞춘 뒤) %": pct(inside_adj),
    }


def run(table: Path, out_dir: Path, today: date) -> dict:
    rows = load_rows(table)
    rows.sort(key=lambda r: (r["sale_date"], r["court_code"], str(r["case_no"]), r["item_no"] or 0))
    first = min(r["sale_date"] for r in rows).replace(day=1)
    last = max(r["sale_date"] for r in rows)
    months = months_range(first, last)
    reduction = read_reduction_pct()
    pool = build_sale_pool(
        rows
    )  # 물건마다 매각일 전 낙찰만 쓰는 것은 rate_range · court_cell 이 함

    variants = {}
    for v in VARIANTS:
        variants[v] = evaluate(variant_rows(rows, v), months, pool, reduction)
    main = variants["all"]
    result = {
        "built_on": today.isoformat(),
        "eval_months": [m["month"] for m in main["monthly"]],
        "parity": parity_check(rows),
        "parity_now": parity_check(rows, engine_from=NOW_ENGINE),
        "variants": variants,
        "monthly": main["monthly"],
        "bid_calibration": main["bid_calibration"],
        "sold_brier": main["sold_brier"],
        "sold_calibration": main["sold_calibration"],
        "importance_last_month": main["importance_last_month"],
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"report_{today:%Y%m%d}.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    summary = _read_summary(table)
    (out_dir / f"report_{today:%Y%m%d}.md").write_text(
        render(result, today, summary), encoding="utf-8"
    )
    return result


def _read_summary(table: Path) -> dict:
    p = table.with_name(table.stem + "_summary.json")
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def _as_dict(p) -> dict | None:
    if p is None:
        return None
    return {"lo": p.p25, "mid": p.p50, "hi": p.p75, "n": p.n, "scope": p.scope}


def _fmt(d: dict | None) -> str:
    return " · ".join(f"{m} {'-' if v is None else v}%" for m, v in (d or {}).items())


def _winner_line(cat: str, w: dict) -> str:
    if w["이긴 방식"] == "표본 적음":
        names = " · ".join(w.get("비교한 방식", []))
        return f"- {cat}: 같은 물건 {w['건수']}건 ({names}) — 표본 적어 가릴 수 없음"
    extra = ""
    if w.get("맞춘 뒤 비교 건수"):
        extra = f" / 범위 안 맞춘 뒤 {_fmt(w['범위 안(맞춘 뒤) %'])} ({w['맞춘 뒤 비교 건수']}건, 같은 건수의 원래 {_fmt(w['그 건수의 범위 안(원래) %'])})"
    return (
        f"- {cat}: **{w['이긴 방식']}** · 같은 물건 {w['건수']}건 ({' · '.join(w['비교한 방식'])}) — "
        f"가운데 오차 {_fmt(w['가운데 오차 %'])} / 범위 안 원래 {_fmt(w['범위 안(원래) %'])}{extra}"
    )


def render(r: dict, today: date, summary: dict | None = None) -> str:
    summary = summary or {}
    lines = [f"# 낙찰가 예측 되짚어 채점 ({today:%Y-%m-%d})", ""]
    p = r["parity"]
    lines.append("## (가) 맞춰 보기 — ① 지금 규칙이 운영과 같은가")
    if not p.get("건수"):
        lines.append(
            "- 입찰 전 분석 스냅샷이 붙은 낙찰이 학습 표에 없어 맞춰 볼 수 없음 → ②③ 비교 결론을 쓰지 않음"
        )
        gate_ok = False
    else:
        lines.append(
            f"스냅샷(analysis.sale_snapshots) 낙찰 {p['건수']}건 · 스냅샷 날짜 {p['스냅샷 날짜'][0]}~{p['스냅샷 날짜'][1]}. "
            "실험실 ① 의 낙찰가율 p25 · p50 · p75(법원 차이 · 최저가 손질 전 원값)와 스냅샷의 analysis->sale_rate 를 견줌, 기준일은 스냅샷 만든 날."
        )
        for name in ("우리 낙찰만(운영과 같은 자료)", "실험실 전체 자료"):
            q = p[name]
            lines.append(
                f"- 비교 사례 {name}: **p50 차이 1%p 안 {q['p50 차이 1%p 안 %']}%** "
                f"(p25 {q['p25 차이 1%p 안 %']}% · p75 {q['p75 차이 1%p 안 %']}% · 표본 수 같음 {q['표본 수(n)가 같은 %']}% · "
                f"p50 차이 가운데 값 {q['p50 차이 가운데 값(%p)']}%p · ① 못 낸 {q['① 이 못 낸 건수']}건)"
            )
            lines.append(f"  - 종류별 p50 1%p 안: {q['종류별 p50 1%p 안 %']}")
        pn = r.get("parity_now") or {}
        qn = pn.get("우리 낙찰만(운영과 같은 자료)") if pn.get("건수") else None
        if qn:
            lines.append(
                f"- 지금 규칙(rules-0.20.0 이상 엔진)으로 만든 스냅샷만({pn['건수']}건, 그 전 엔진 스냅샷은 유찰 횟수 셈 등 규칙이 달랐음): "
                f"**p50 차이 1%p 안 {qn['p50 차이 1%p 안 %']}%** (표본 수 같음 {qn['표본 수(n)가 같은 %']}% · "
                f"p50 차이 가운데 값 {qn['p50 차이 가운데 값(%p)']}%p)"
            )
        gate = (
            qn["p50 차이 1%p 안 %"]
            if qn
            else p["우리 낙찰만(운영과 같은 자료)"]["p50 차이 1%p 안 %"]
        )
        gate_ok = gate > 90
        lines.append(
            f"- 판정(기준: 지금 규칙 스냅샷 · 운영과 같은 자료로 90% 초과): **{'통과' if gate_ok else '미달 — 원인을 찾을 때까지 ②③ 비교 결론을 쓰지 않음'}**"
        )
    lines.append("")
    lines.append("## (나) 종류마다 이긴 방식 — 같은 물건끼리 (가운데 오차 · 범위 안 둘 다)")
    if not gate_ok:
        lines.append("※ (가) 가 통과하지 않아 아래는 참고용 숫자일 뿐 결론이 아님.")
    for v, label in VARIANTS.items():
        lines.append("")
        lines.append(f"### 시세: {label}")
        for cat in CATS:
            lines.append(_winner_line(cat, r["variants"][v]["winners"][cat]))
    lines += [
        "",
        f"평가 달: {', '.join(r['eval_months']) or '없음'} (첫 달은 배움용). 범위 안 「맞춘 뒤」는 k 를 구할 수 있었던(지난 성적 30건 이상) 달의 물건만.",
        "",
    ]

    chk = summary.get("rounds_check")
    lines.append("## ① 의 유찰 횟수 · 시세 붙이기 — 어떻게 했나")
    if chk:
        lines.append(
            f"- 우리 자료: 운영과 같은 price_round. 강사 자료: 최저가로 센 값(DB 의 price_round 와 같은 셈) — "
            f"우리 자료와 겹치는 물건 {chk['같은 물건(우리 자료에도 있음)']}건에서 쓴 값이 우리 price_round 와 같은 것 {chk['쓴 값(eff_failed)이 price_round 와 같음']}건."
        )
        lines.append(
            f"- 못 센 물건(저감률을 모르는 법원 · 정수로 안 떨어짐)에 쓸 값은 센 물건 {chk.get('최저가로 센 물건 수')}건에서 후보마다 맞은 비율을 재서 "
            f"골랐다: {chk.get('후보별 맞은 비율')} → **{chk.get('못 센 물건에 쓴 후보')}**. "
            "(yuchal=법원 yuchalCnt, yuchal-1=그 값−1, prior=같은 물건의 앞 매각기일 줄 수 — 자료가 17주치라 앞 기일이 모자랄 수 있음)"
        )
    mc = summary.get("market_by_category")
    if mc:
        lines.append(
            "- 시세가 붙은 줄 수(종류마다, 지번 찾은 방법별 — maejibun=(a) · items=(b) · geo=(c) · name=(d)):"
        )
        for c, d in mc.items():
            lines.append(f"  - {c}: 전체 {d['rows']}줄 중 {d['with_market']}줄 · {d.get('by_how')}")
    g = summary.get("geocode")
    if g:
        lines.append(f"- 역지오코딩(c): {g}")
    lines.append("")

    lines.append("## 종류별 성적 (전체 달 합산)")
    for v, label in VARIANTS.items():
        lines.append("")
        lines.append(f"### 시세: {label}")
        lines.append(
            "| 종류 | 방식 | 건수 | 범위 안(원래) % | 낮게 % | 높게 % | 가운데 오차 % | 10%p 넘게 틀린 % | 맞춘 건수 | 그 물건들 원래 범위 안 % | 맞춘 뒤 범위 안 % |"
        )
        lines.append("|---|---|---|---|---|---|---|---|---|---|---|")
        for cat in ["전체", *CATS]:
            for meth in METHODS:
                m = r["variants"][v]["pooled"].get(cat, {}).get(meth)
                if not m or m.get("건수", 0) == 0:
                    lines.append(f"| {cat} | {meth} | 0 | - | - | - | - | - | - | - | - |")
                    continue
                lines.append(
                    f"| {cat} | {meth} | {m['건수']} | {m['범위 안(25~75%) %']} | {m['낮게 %']} | {m['높게 %']} | {m['가운데 오차 %']} | {m['10%p 넘게 틀린 %']} "
                    f"| {m['맞춘 건수']} | {m.get('그 물건들 원래 범위 안 %', '-')} | {m.get('그 물건들 맞춘 뒤 범위 안 %', '-')} |"
                )
    lines.append("")
    lines.append(
        "## 범위 폭 배수 k (지난달까지 성적으로 정함 — 비어 있으면 지난 성적 30건 미만이라 안 맞춤)"
    )
    lines.append("| 방식 | 종류 | " + " | ".join(r["eval_months"]) + " |")
    lines.append("|---|---|" + "---|" * len(r["eval_months"]))
    for key, byk in r["variants"]["all"]["k_table"].items():
        meth, cat = key.split("|")
        if any(v is not None for v in byk.values()):
            lines.append(
                f"| {meth} | {cat} | "
                + " | ".join(
                    "-" if byk.get(mo) is None else str(byk[mo]) for mo in r["eval_months"]
                )
                + " |"
            )
    lines.append("")
    lines.append("## 달마다 성적 (전체 종류, 시세 전체)")
    lines.append("| 달 | 방식 | 건수 | 범위 안 % | 가운데 오차 % | 10%p 넘게 틀린 % |")
    lines.append("|---|---|---|---|---|---|")
    for mon in r["eval_months"]:
        for meth in METHODS:
            m = r["variants"]["all"]["per_month"].get("전체", {}).get(meth, {}).get(mon)
            if m and m.get("건수"):
                lines.append(
                    f"| {mon} | {meth} | {m['건수']} | {m['범위 안(25~75%) %']} | {m['가운데 오차 %']} | {m['10%p 넘게 틀린 %']} |"
                )
    lines.append("")
    lines.append("## 제외 건수 (방식별 · 종류별, 낙찰 건 기준, 시세 전체)")
    for k, n in sorted(r["variants"]["all"]["excluded"].items()):
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
        "주의: 단지 이름(d)으로 붙인 시세는 이름이 같은 다른 동 · 다른 필지를 섞을 수 있다. 그래서 위 결과를 「전체」와 「지번만」 둘로 나눠 냈다."
    )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    tables = sorted(LAB_DIR.glob("table_????????.parquet"))
    if not tables:
        sys.exit("학습 표가 없습니다. 먼저 build_table.py 를 실행하세요.")
    latest = tables[-1]
    today = date.today()
    res = run(latest, LAB_DIR, today)
    print(render(res, today, _read_summary(latest)))
