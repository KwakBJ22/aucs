"""처음 나온 물건(회차 0) 따로 채점: 시세 · 감정가 차이를 쓰는 방식이 낙찰가율 통계보다 잘 맞히는지.

대상: 최저가율로 센 회차가 0 인 물건. 낙찰은 가격 채점, 낙찰 + 유찰은 팔릴 확률 채점. 가격 범위는 모든 방식에서 감정가 밑으로 안 감.
방식(같은 물건끼리): ① 지금 규칙 · ④ 새 방식 · ⑤ 사다리(지금 것 그대로) · ② 시세 기준(신건판) · ⑥ 감정가÷시세 구간 · ⑥+⑤ 섞음 ·
③ 머신러닝(지금 모형, 그리고 회차 0 만으로 따로 배운 신건 전용 모형). 비교 사례 · 배움은 입찰일 전 365일 안 자료만.

실행(저장소 맨 위에서): uv run --no-project --with lightgbm --with scikit-learn --with pandas --with pyarrow --with-editable packages/rules python tools/predict_lab/backtest_new.py
결과: data\\predict_lab\\report_YYYYMMDD_new.md · report_YYYYMMDD_new.json
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

import backtest as bt
from backtest import CATS, MARKET_CATS, METHODS, item_key, load_rows
from ladder import add_ladder_rounds
from methods import brier, build_sale_pool, calibration, months_range
from newitem import (
    NewItemIndex,
    band_table,
    clip_floor,
    mix_band_ladder,
    new_targets,
    p_sold_band,
    predict_band,
    predict_market_new,
)
from paths import LAB_DIR

M1, M3, M4, M5 = METHODS[0], METHODS[2], METHODS[3], METHODS[4]
M2N = "②시세 기준(신건판)"
M3N = "③신건 전용 모형"
M6 = "⑥감정가÷시세 구간"
M65 = "⑥+⑤ 섞음"
NEW_MIN_N = 50  # 종류마다 같은 물건이 이보다 적으면 「표본 적음」 — 숫자는 참고로만 내고 이긴 방식은 안 정함
ML_NEW_MIN_SOLD = 300  # 신건 전용 모형: 배움 자료(회차 0 낙찰)가 이보다 적으면 안 배움
# 1회 이상(신건 아님) 물건에 쓰는 종류별 이긴 방식(지난 보고서 report_20261128): 아파트 ③ · 그 밖 ⑤ · 나머지도 ⑤
REST_WINNER = {c: M5 for c in CATS} | {"아파트": M3}
GROUP_A = (M1, M2N, M3, M4, M5, M6)  # 시세 있는 신건(아파트 · 빌라 · 오피스텔) — 같은 물건끼리
GROUP_B = (M1, M3, M4, M5, M65)  # 모든 신건(시세 없는 것 포함)
GROUP_C = (M1, M3, M3N, M4, M5, M65)  # 신건 전용 모형이 배운 달의 물건


def _clip_rec(rec: dict) -> dict:
    """채점 행의 범위를 감정가 밑으로 안 내려가게(감정가는 낙찰가 ÷ 낙찰가율에서 되짚음)."""
    app = rec["actual"] * 100 / rec["actual_ratio"]
    out = dict(rec)
    for k in ("lo", "mid", "hi"):
        out[k] = max(out[k], app)
    out["pred_mid_ratio"] = out["mid"] * 100 / app
    return out


def _mk(t: dict, p: dict, method: str) -> dict:
    return {
        **bt._rec_of(t, p),
        "method": method, "cat": t["category"], "item": item_key(t),
        "floor": t.get("min_price_krw"), "lo_adj": None, "hi_adj": None, "k": None,
    }  # fmt: skip


def compare(
    by_item: dict[str, dict[str, dict]], methods: tuple[str, ...], min_n: int = NEW_MIN_N
) -> dict:
    """같은 물건끼리(고른 방식이 모두 낸 물건) 방식마다 성적. 건수가 min_n 미만이면 이긴 방식을 안 정한다."""
    items = [v for v in by_item.values() if all(m in v for m in methods)]
    n = len(items)
    stats = {m: bt._err_metrics([v[m] for v in items]) for m in methods} if n else {}
    best = best_mid = None
    if n >= min_n:
        best = min(methods, key=lambda m: stats[m]["평균 오차 %p"])
        best_mid = min(methods, key=lambda m: stats[m]["가운데 오차 %"])
    return {
        "건수": n,
        "few": n < min_n,
        "stats": stats,
        "이긴 방식": best,
        "가운데 오차 기준": best_mid,
        "방식": list(methods),
    }


def _group(flat: dict[str, dict[str, dict[str, dict]]], cat: str, methods: tuple[str, ...]) -> dict:
    return compare(flat.get(cat, {}), methods)


def _prob_block(pairs_by_method: dict[str, list[tuple[float, int]]]) -> dict:
    return {
        m: {"건수": len(p), "Brier": round(brier([a for a, _ in p], [y for _, y in p]), 4) if p else None, "칸": calibration(p)}
        for m, p in pairs_by_method.items()
    }  # fmt: skip


def run_new(table: Path, out_dir: Path, today: date) -> dict:
    import ml

    rows = load_rows(table)
    rows.sort(key=lambda r: (r["sale_date"], r["court_code"], str(r["case_no"]), r["item_no"] or 0))
    months = months_range(
        min(r["sale_date"] for r in rows).replace(day=1), max(r["sale_date"] for r in rows)
    )
    add_ladder_rounds(rows, bt.read_reduction_all())
    reduction = bt.read_reduction_pct()
    pool = build_sale_pool(rows)

    # 지금 방식 그대로(①②③④⑤) — 지난 보고서와 같은 길. ④⑤ 는 6조합 중 가장 나았던 조합.
    lpreds, ltargets = bt.ladder_predictions(rows, months[1])
    best = bt.combo_table(lpreds, ltargets)["best"]
    ev = bt.evaluate(rows, months, pool, reduction, lpreds[(best[0], bool(best[1]))])
    records, sold_items = ev["_records"], ev["_sold_items"]

    targets = new_targets(rows, months[1])
    new_keys = {item_key(t) for t in targets}
    tkey = {item_key(t): t for t in targets}
    recmap: dict[str, dict[str, dict]] = defaultdict(dict)  # 물건 → 방식 → 채점 행
    for rec in records:
        if rec["item"] in new_keys and rec["method"] != METHODS[1]:
            recmap[rec["item"]][rec["method"]] = _clip_rec(rec)

    # ②⑥⑥+⑤ (신건판) — 비교 사례는 입찰일 앞선 365일 안 회차 0 낙찰
    index = NewItemIndex(rows)
    for t in targets:
        if t["result"] != "sold" or not t.get("winning_bid_krw"):
            continue
        key = item_key(t)
        p2, p6 = predict_market_new(index, t), predict_band(index, t)
        if p2:
            recmap[key][M2N] = _mk(t, p2, M2N)
        if p6:
            recmap[key][M6] = _mk(t, p6, M6)
        r5 = recmap[key].get(M5)
        if p6 is not None:
            recmap[key][M65] = _mk(t, mix_band_ladder(p6, None), M65)
        elif r5 is not None:
            recmap[key][M65] = {**r5, "method": M65}

    # ③ 신건 전용 모형 — 달마다 그 달 전 365일 안 회차 0 자료로(낙찰 300건 이상일 때만)
    p_new: dict[str, float] = {}
    ml_meta = []
    for m in months[1:]:
        nxt = bt.next_month(m)
        train = [
            r
            for r in rows
            if r.get("ladder_round") == 0 and m - timedelta(days=365) <= r["sale_date"] < m
        ]
        sold_n = sum(1 for r in train if r["result"] == "sold")
        test = [t for t in targets if m <= t["sale_date"] < nxt]
        trained = sold_n >= ML_NEW_MIN_SOLD and bool(test)
        ml_meta.append(
            {
                "month": f"{m:%Y-%m}",
                "배움 낙찰": sold_n,
                "배움 전체": len(train),
                "맞힐 신건": len(test),
                "배웠나": trained,
            }
        )
        if not trained:
            continue
        model = ml.fit(train)
        for t, mp in zip(test, ml.predict(model, test), strict=True):
            key = item_key(t)
            p_new[key] = mp["p_sold"]
            if t["result"] == "sold" and t.get("winning_bid_krw"):
                app, q = float(t["appraisal_krw"]), mp["ratio_q"]
                p = clip_floor(
                    {"lo": app * q[1] / 100, "mid": app * q[2] / 100, "hi": app * q[3] / 100}, app
                )
                recmap[key][M3N] = _mk(t, p, M3N)

    # 종류별로 모으기(같은 물건끼리 비교용)
    flat: dict[str, dict[str, dict[str, dict]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(dict))
    )
    for key, ms in recmap.items():
        cat = tkey[key]["category"]
        for meth, rec in ms.items():
            flat[cat][key][meth] = rec
            flat["전체"][key][meth] = rec
    groups_a = {c: _group(flat, c, GROUP_A) for c in MARKET_CATS}
    groups_b = {
        c: _group(flat, c, tuple(m for m in GROUP_B if not (c == "그 밖" and m == M3)))
        for c in (*CATS, "전체")
    }
    groups_c = {c: _group(flat, c, GROUP_C) for c in ("전체", *MARKET_CATS)}

    counts = {}
    for c in CATS:
        ts = [t for t in targets if t["category"] == c]
        sold = [t for t in ts if t["result"] == "sold"]
        counts[c] = {
            "낙찰": len(sold), "유찰": sum(1 for t in ts if t["result"] == "failed"),
            "낙찰 중 시세 붙음": sum(1 for t in sold if t.get("market_price_krw")),
            "유찰 중 시세 붙음": sum(1 for t in ts if t["result"] == "failed" and t.get("market_price_krw")),
        }  # fmt: skip
    sold_all = [t for t in targets if t["result"] == "sold" and t.get("sale_rate") is not None]
    below100 = sum(1 for t in sold_all if t["sale_rate"] < 100)

    # 팔릴 확률(신건): 현행 모형 vs 구간별 실제 팔린 비율 (vs 신건 전용 모형)
    cur = {it["item"]: it for it in sold_items if it["item"] in new_keys}
    pairs: dict[str, list[tuple[float, int]]] = {"현행 모형": [], "구간별 팔린 비율": []}
    pairs3: dict[str, list[tuple[float, int]]] = {
        "현행 모형": [],
        "구간별 팔린 비율": [],
        "신건 전용 모형": [],
    }
    for t in targets:
        key = item_key(t)
        pc, pb, pn = (cur.get(key) or {}).get("p"), p_sold_band(index, t), p_new.get(key)
        y = 1 if t["result"] == "sold" else 0
        if pc is not None and pb is not None:
            pairs["현행 모형"].append((pc, y))
            pairs["구간별 팔린 비율"].append((pb, y))
            if pn is not None:
                pairs3["현행 모형"].append((pc, y))
                pairs3["구간별 팔린 비율"].append((pb, y))
                pairs3["신건 전용 모형"].append((pn, y))
    probs = {
        "같은 신건끼리(현행 vs 구간별)": _prob_block(pairs),
        "신건 전용 모형이 배운 달": _prob_block(pairs3),
    }

    bands = band_table([r for r in rows])
    mixed = _mixed(rows, records, recmap, groups_b, tkey)

    result = {
        "built_on": today.isoformat(), "eval_months": [f"{m:%Y-%m}" for m in months[1:]],
        "ladder_combo": {"N": best[0], "이상치 뺌": bool(best[1])},
        "counts": counts, "below100": {"낙찰": len(sold_all), "낙찰가율 100 미만": below100},
        "group_a": groups_a, "group_b": groups_b, "group_c": groups_c,
        "bands": bands, "probs": probs, "ml_new": ml_meta, "mixed": mixed,
    }  # fmt: skip
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"report_{today:%Y%m%d}_new.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    (out_dir / f"report_{today:%Y%m%d}_new.md").write_text(
        render_new(result, today), encoding="utf-8"
    )
    return result


def _mixed(rows: list[dict], records: list[dict], recmap: dict, groups_b: dict, tkey: dict) -> dict:
    """신건은 이긴 방식(종류마다, 위 그룹 B) · 나머지는 종류별 이긴 방식(아파트 ③ · 나머지 ⑤)으로 섞어 낸 전체 성적 vs ① 하나로만."""
    by_key = {item_key(r): r for r in rows if r["result"] == "sold"}
    raw: dict[str, dict[str, dict]] = defaultdict(dict)
    for rec in records:
        raw[rec["item"]][rec["method"]] = rec
    new_pick = {
        c: (g["이긴 방식"] or M5) for c, g in groups_b.items() if c != "전체"
    }  # 표본 적은 종류는 ⑤
    mix_recs, base_recs, mix_new, base_new, mix_rest, base_rest = [], [], [], [], [], []
    fallback = 0
    for key, ms in raw.items():
        base = ms.get(M1)
        if base is None or key not in by_key:
            continue
        r = by_key[key]
        cat = r["category"]
        if key in tkey:  # 신건: 감정가 밑으로 안 가게 한 신건 채점 행을 씀
            pool_ms, pick = recmap.get(key, {}), new_pick.get(cat, M5)
        else:
            pool_ms, pick = ms, REST_WINNER.get(cat, M5)
        chosen = pool_ms.get(pick)
        if chosen is None:
            chosen, fallback = base, fallback + 1
        mix_recs.append(chosen)
        base_recs.append(base)
        (mix_new if key in tkey else mix_rest).append(chosen)
        (base_new if key in tkey else base_rest).append(base)
    m = bt._err_metrics
    return {
        "건수": len(mix_recs), "고른 방식이 없어 ① 로 대신한 건수": fallback,
        "신건 고른 방식": new_pick, "나머지 고른 방식": REST_WINNER,
        "섞음": m(mix_recs), "① 하나로": m(base_recs),
        "신건만": {"섞음": m(mix_new), "① 하나로": m(base_new)},
        "나머지만": {"섞음": m(mix_rest), "① 하나로": m(base_rest)},
    }  # fmt: skip


def _row(label: str, cat: str, g: dict) -> list[str]:
    if not g["건수"]:
        return [f"| {cat} | 0 | {label} | - | - | - | - | - | |"]
    out = []
    for i, meth in enumerate(g["방식"]):
        s = g["stats"][meth]
        mark = (
            "◀ 이김"
            if meth == g["이긴 방식"]
            else ("(가운데 오차 기준 이김)" if meth == g["가운데 오차 기준"] else "")
        )
        first = i == 0
        out.append(
            f"| {cat if first else ''} | {g['건수'] if first else ''}{' (표본 적음 — 참고만)' if first and g['few'] else ''} | {meth} | {s['평균 오차 %p']} | {s['가운데 값 %p']} "
            f"| {s['10%p 넘게 틀린 %']} | {s['가운데 오차 %']} | {s['범위 안(25~75%) %']} | {mark} |"
        )
    return out


HEAD = "| 종류 | 같은 물건 건수 | 방식 | 평균 오차 %p | 가운데 값 %p | 10%p 넘게 틀린 % | 가운데 오차 % | 범위 안 % | 이김 |\n|---|---|---|---|---|---|---|---|---|"


def render_new(r: dict, today: date) -> str:
    L = [f"# 처음 나온 물건 따로 채점 ({today:%Y-%m-%d})", ""]
    b = r["below100"]
    L.append(
        "**처음 나온 물건 = 최저가율로 센 회차 0.** 최저가 = 감정가라 낙찰은 감정가 이상으로 팔린다(낙찰 "
        f"{b['낙찰']}건 중 낙찰가율 100 미만은 {b['낙찰가율 100 미만']}건 — 최저가율이 98~100% 인 줄이 섞여서). "
        "그래서 가격 범위는 모든 방식에서 감정가 밑으로 안 내린다. 평가 달 "
        + ", ".join(r["eval_months"])
        + f" · ④⑤ 는 N={r['ladder_combo']['N']} 조합. "
        "시세는 지난 보고서의 「전체(지번 + 단지 이름)」 묶음."
    )
    L += [
        "",
        "## 종류마다 신건 건수 · 시세 붙은 수",
        "",
        "| 종류 | 낙찰 | 유찰 | 낙찰 중 시세 붙음 | 유찰 중 시세 붙음 |",
        "|---|---|---|---|---|",
    ]
    for c, v in r["counts"].items():
        L.append(
            f"| {c} | {v['낙찰']} | {v['유찰']} | {v['낙찰 중 시세 붙음']} | {v['유찰 중 시세 붙음']} |"
        )
    L += [
        "",
        "## 시세 있는 신건 — 같은 물건끼리 ①②③④⑤⑥",
        "",
        "이긴 방식 = 평균 오차(%p) 가장 작은 방식. 같은 물건이 50건 미만이면 숫자는 참고로만 내고 이긴 방식은 안 정함.",
        "",
        HEAD,
    ]
    for c, g in r["group_a"].items():
        L += _row("", c, g)
    L += [
        "",
        "## 모든 신건(시세 없는 것 포함) — ①③④⑤ 와 ⑥+⑤ 섞음(시세 있으면 ⑥, 없으면 ⑤)",
        "",
        HEAD,
    ]
    for c, g in r["group_b"].items():
        L += _row("", c, g)
    L += ["", "## 신건 전용 모형(③) — 배운 달의 물건만", ""]
    for m in r["ml_new"]:
        L.append(
            f"- {m['month']}: 배움 낙찰 {m['배움 낙찰']}건(전체 {m['배움 전체']}) · 맞힐 신건 {m['맞힐 신건']}건 → {'배웠음' if m['배웠나'] else '표본 적음(낙찰 300건 미만) — 결론 안 냄'}"
        )
    L += ["", HEAD]
    for c, g in r["group_c"].items():
        L += _row("", c, g)
    L += [
        "",
        "## 감정가 ÷ 시세 구간표 (설명용 — 시기를 안 가르고 시세 붙은 신건 전부)",
        "",
        "| 구간 | 신건 | 낙찰 | 팔린 비율 % | 낙찰가율 가운데 값 % |",
        "|---|---|---|---|---|",
    ]
    for v in r["bands"]:
        L.append(
            f"| {v['구간']} | {v['신건']} | {v['낙찰']} | {v['팔린 비율 %']} | {v['낙찰가율 가운데 값 %']} |"
        )
    sold = [v["팔린 비율 %"] for v in r["bands"] if v["팔린 비율 %"] is not None]
    mono = all(a >= b2 for a, b2 in zip(sold, sold[1:], strict=False))
    top = r["bands"][-1]
    allv = sum(v["낙찰"] for v in r["bands"]) * 100 / max(sum(v["신건"] for v in r["bands"]), 1)
    L += [
        "",
        f"짐작(시세가 감정가보다 많이 낮은 신건 = 감정가 ÷ 시세가 큰 구간은 거의 유찰된다): 1.1 이상 구간 팔린 비율 {top['팔린 비율 %']}%({top['신건']}건) · 전체 {allv:.1f}% · "
        f"구간이 올라갈수록 팔린 비율이 계속 내려가는가: **{'예' if mono else '아니오'}**.",
        "",
        "## 팔릴 확률(신건) — 현행 모형 vs 구간별 실제 팔린 비율",
        "",
        "Brier 점수는 낮을수록 잘 맞는다. 같은 신건(시세 있고 두 값 다 나온 물건, 낙찰 + 유찰)끼리.",
        "",
    ]
    for title, blk in r["probs"].items():
        L += [f"### {title}", "", "| 방식 | 건수 | Brier |", "|---|---|---|"]
        for m, v in blk.items():
            L.append(f"| {m} | {v['건수']} | {v['Brier']} |")
        for m, v in blk.items():
            L += [
                "",
                f"{m} — 10% 칸 점검",
                "",
                "| 예측 칸 | 건수 | 예측 평균 | 실제 비율 |",
                "|---|---|---|---|",
            ]
            L += [
                f"| {c['칸']} | {c['건수']} | {c['예측 평균']} | {c['실제 비율']} |"
                for c in v["칸"]
            ]
        L.append("")
    x = r["mixed"]
    L += [
        "## 마지막 — 신건은 이긴 방식 · 나머지는 종류별 이긴 방식으로 섞어 냈을 때",
        "",
        f"신건은 종류마다 위 「모든 신건」에서 이긴 방식({x['신건 고른 방식']}), 나머지(1회 이상)는 종류별 이긴 방식({x['나머지 고른 방식']}, 지난 보고서 기준). 고른 방식이 값을 안 낸 {x['고른 방식이 없어 ① 로 대신한 건수']}건은 ① 로 대신. 같은 물건 {x['건수']}건.",
        "",
        "| 범위 | 방식 | 건수 | 평균 오차 %p | 10%p 넘게 틀린 % | 가운데 오차 % |",
        "|---|---|---|---|---|---|",
    ]
    for label, a, bb in (
        ("전체", x["섞음"], x["① 하나로"]),
        ("신건만", x["신건만"]["섞음"], x["신건만"]["① 하나로"]),
        ("나머지만", x["나머지만"]["섞음"], x["나머지만"]["① 하나로"]),
    ):
        for name, s in (("섞음", a), ("① 하나로", bb)):
            if s.get("건수"):
                L.append(
                    f"| {label} | {name} | {s['건수']} | {s['평균 오차 %p']} | {s['10%p 넘게 틀린 %']} | {s['가운데 오차 %']} |"
                )
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    tables = sorted(LAB_DIR.glob("table_????????.parquet"))
    if not tables:
        sys.exit("학습 표가 없습니다. 먼저 build_table.py 를 실행하세요.")
    res = run_new(tables[-1], LAB_DIR, date.today())
    print((LAB_DIR / f"report_{date.today():%Y%m%d}_new.md").read_text(encoding="utf-8"))
