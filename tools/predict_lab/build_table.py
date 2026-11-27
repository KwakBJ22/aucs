"""학습 표 만들기: 강사 자료 + 우리 자료 → 낙찰 · 유찰 한 줄씩 → data\\predict_lab\\table_YYYYMMDD.parquet

실행(저장소 맨 위에서): uv run --no-project --with-editable packages/rules --with pandas --with pyarrow python tools/predict_lab/build_table.py
처음 한 번은 export_ours.py 로 우리 자료를 내려받아야 한다(src\\우리_낙찰.parquet).
"""

import json
import sqlite3
import sys
from collections import Counter
from datetime import date
from pathlib import Path

from market import REAL_KIND, find_jibun, load_trade_index, market_for_row, umd_by_sgg
from paths import (
    INSTRUCTOR_DB,
    ITEMS_PARQUET,
    LAB_DIR,
    OURS_PARQUET,
    REDUCTION_JSON,
    SGG_JSON,
)
from table import (
    Geo,
    apply_filters,
    choose_fallback,
    code_pairs_instructor,
    group_instructor,
    implied_rounds,
    instructor_row,
    item_key,
    merge,
    ours_row,
    prior_date_counts,
)
from usage import code_majority

MARKET_YEARS = range(2024, 2027)  # 기준일 24개월 전까지 필요


def read_instructor(path: Path = INSTRUCTOR_DB) -> list[dict]:
    con = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in con.execute("select * from sale_result")]
    finally:
        con.close()


def read_ours(path: Path = OURS_PARQUET) -> list[dict]:
    import pandas as pd

    df = pd.read_parquet(path)
    df = df.astype(object).where(pd.notna(df), None)
    return df.to_dict("records")


def geo_table() -> Geo:
    """시군구 이름 표(실거래 sgg.json) + 법정동 목록으로 법원 지역 이름을 코드로 바꾸는 표."""
    names = json.loads(SGG_JSON.read_text(encoding="utf-8"))["names"]
    return Geo(names, umd_by_sgg(set(names), range(2025, 2027)))


def add_market(rows: list[dict], index, items_addr: dict, geo_cache: dict | None) -> Counter:
    """각 행에 당시 시세를 붙인다. 못 붙인 이유 · 찾은 방법(market_how)을 센다."""
    why: Counter = Counter()
    for r in rows:
        r["market_price_krw"] = None
        r["market_level"] = None
        r["market_n"] = None
        r["market_how"] = None  # maejibun(a) · items(b) · geo(c) · name(d)
        r["market_ratio"] = None  # 시세 ÷ 감정가 × 100
        r["appraisal_over_market"] = None  # 감정가 ÷ 시세
        r["win_over_market"] = None  # 낙찰가 ÷ 시세 (낙찰 건만)
        r["sale_month"] = f"{r['sale_date']:%Y-%m}"
        if r["category"] not in REAL_KIND:
            why["종류에 시세 없음"] += 1
            continue
        m, how = market_for_row(index, r, items_addr, geo_cache)
        if m is None:
            why["비교 거래 없음"] += 1
            continue
        r["market_price_krw"] = m.price_krw
        r["market_level"] = m.level
        r["market_n"] = m.n
        r["market_how"] = how
        r["market_ratio"] = round(m.price_krw * 100 / r["appraisal_krw"], 2)
        r["appraisal_over_market"] = round(r["appraisal_krw"] / m.price_krw, 4)
        if r["winning_bid_krw"]:
            r["win_over_market"] = round(r["winning_bid_krw"] / m.price_krw, 4)
        why["붙음"] += 1
    return why


def _to_int_or_none(v) -> int | None:
    try:
        return int(float(str(v).replace(",", "").strip()))
    except (TypeError, ValueError):
        return None


def read_items_addr(path: Path = ITEMS_PARQUET) -> dict[tuple, str]:
    import pandas as pd

    df = pd.read_parquet(path)
    return {
        (r.court_code, r.case_no, int(r.item_no)): r.address
        for r in df.itertuples()
        if r.address and r.item_no == r.item_no
    }


def read_reduction(path: Path = REDUCTION_JSON) -> dict:
    return (
        json.loads(path.read_text(encoding="utf-8"))
        if path.exists()
        else {"pct": {}, "verified": []}
    )


def rounds_check(court: list[dict], ours: list[dict]) -> dict:
    """강사 유찰 횟수 정하기 점검: 우리 자료와 같은 물건(둘 다 있는 것)에서 우리 price_round 에 어느 쪽이 맞는가."""
    twin = {item_key(r): r for r in ours if r["price_round"] is not None}
    n = same_yuchal = same_prior = same_eff = prior_known = 0
    for r in court:
        t = twin.get(item_key(r))
        if t is None:
            continue
        n += 1
        same_yuchal += r["failed_count"] == t["price_round"]
        same_eff += r["eff_failed"] == t["price_round"]
        if r["prior_dates"]:  # 앞 기일이 자료 안에 있는 것만 견줌(없으면 0 이라 당연히 틀림)
            prior_known += 1
            same_prior += r["prior_dates"] == t["price_round"]
    return {
        "같은 물건(우리 자료에도 있음)": n,
        "법원 숫자(yuchalCnt)가 우리 price_round 와 같음": same_yuchal,
        "앞 기일이 자료에 있는 물건": prior_known,
        "그중 앞 기일 수가 price_round 와 같음": same_prior,
        "쓴 값(eff_failed)이 price_round 와 같음": same_eff,
        "정한 방법별 줄 수": dict(Counter(r["eff_how"] for r in court)),
    }


def build(out_dir: Path = LAB_DIR, today: date | None = None, geocode: bool = True) -> dict:
    import geo as geomod
    import pandas as pd

    today = today or date.today()
    raw = read_instructor()
    grouped, conflicts = group_instructor(raw)
    code_map = code_majority(code_pairs_instructor(raw))
    geo = geo_table()
    red = read_reduction()
    prior = prior_date_counts(grouped)
    # 유찰 횟수: 최저가로 센 값이 기준. 못 세는 물건에 쓸 후보는 세는 물건들에서 가장 잘 맞은 것으로 고른다
    samples = []
    for g in grouped:
        yu = _to_int_or_none(g.get("yuchalCnt"))
        imp = implied_rounds(
            g["boCd"],
            _to_int_or_none(g.get("gamevalAmt")),
            _to_int_or_none(g.get("minmaePrice")),
            yu,
            red["pct"],
        )
        if imp is not None:
            samples.append(
                (imp, yu, prior.get((g["boCd"], g["saNo"], g["maemulSer"], str(g["maeGiil"]))))
            )
    fallback, fallback_rates = choose_fallback(samples)
    court = [instructor_row(g, geo, code_map, red["pct"], prior, fallback) for g in grouped]
    ours = [ours_row(r, code_map, geo) for r in read_ours()]
    checks = rounds_check(court, ours)
    merged, overlap = merge(court, ours)
    kept, dropped = apply_filters(merged)

    items_addr = read_items_addr()
    sgg_codes = {r["sgg"] for r in kept if r["sgg"]}
    index = load_trade_index(sgg_codes, MARKET_YEARS)

    # (c) 좌표로 지번 찾기: (a)(b)로 지번을 못 찾은 시세 대상 줄의 좌표만 브이월드에 묻는다(캐시에 있으면 안 물음)
    need = {
        (r["kx"], r["ky"])
        for r in kept
        if r["category"] in REAL_KIND
        and r["sgg"]
        and r["area_m2"]
        and r["kx"]
        and r["ky"]
        and find_jibun(r, items_addr, None)[2] == "name"
    }
    geo_run = {"좌표 종류 수(지번 못 찾은 줄)": len(need)}
    if geocode and need:
        geo_run.update(geomod.geocode_missing(sorted(need), today))
        print("역지오코딩:", geo_run)
    geo_cache = geomod.load_cache()
    market_why = add_market(kept, index, items_addr, geo_cache)

    df = pd.DataFrame(kept).sort_values(["sale_date", "court_code", "case_no", "item_no"])
    out = out_dir / f"table_{today:%Y%m%d}.parquet"
    out_dir.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out, index=False)

    by_how = {
        c: df[(df["category"] == c) & df["market_how"].notna()]["market_how"]
        .value_counts()
        .to_dict()
        for c in ("아파트", "빌라", "오피스텔")
    }
    # 지오코딩 점검: 브이월드가 돌려준 법정동이 법원 자료의 법정동과 같은 비율(같은 건물을 가리켰는지의 거친 증거)
    geo_rows = [
        r
        for r in kept
        if r["src"] == "court" and r["kx"] and geomod.lookup(geo_cache, r["kx"], r["ky"])
    ]
    geo_same = sum(
        1
        for r in geo_rows
        if r["umd"] and geomod.lookup(geo_cache, r["kx"], r["ky"])[0] == r["umd"]
    )
    summary = {
        "built_on": f"{today:%Y-%m-%d}",
        "rows_saved": len(df),
        "instructor_raw_rows": len(raw),
        "instructor_grouped_items": len(grouped),
        "instructor_group_conflicts": conflicts,
        "sgg_unmatched_instructor_items": sum(1 for r in court if r["sgg"] is None),
        "ours_rows": len(ours),
        "overlap": overlap,
        "dropped": dict(dropped),
        "by_category": df["category"].value_counts().to_dict(),
        "by_result": df["result"].value_counts().to_dict(),
        "market_coverage": dict(market_why),
        "market_by_category": {
            c: {
                "rows": int((df["category"] == c).sum()),
                "with_market": int(((df["category"] == c) & df["market_price_krw"].notna()).sum()),
                "by_how": by_how[c],  # maejibun(a) · items(b) · geo(c) · name(d)
            }
            for c in ("아파트", "빌라", "오피스텔")
        },
        "geocode": geo_run
        | {"지오코딩 결과가 있는 줄": len(geo_rows), "그중 법정동이 법원 자료와 같음": geo_same},
        "rounds_check": checks
        | {
            "최저가로 센 물건 수": len(samples),
            "후보별 맞은 비율": {k: round(v, 4) for k, v in fallback_rates.items()},
            "못 센 물건에 쓴 후보": fallback,
        },
        "date_range": [f"{df['sale_date'].min()}", f"{df['sale_date'].max()}"],
    }
    (out_dir / f"table_{today:%Y%m%d}_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    return summary


if __name__ == "__main__":
    s = build(geocode="--no-geocode" not in sys.argv)
    print(json.dumps(s, ensure_ascii=False, indent=2, default=str))
