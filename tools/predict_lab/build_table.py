"""학습 표 만들기: 강사 자료 + 우리 자료 → 낙찰 · 유찰 한 줄씩 → data\\predict_lab\\table_YYYYMMDD.parquet

실행(저장소 맨 위에서): uv run --no-project --with-editable packages/rules --with pandas --with pyarrow python tools/predict_lab/build_table.py
처음 한 번은 export_ours.py 로 우리 자료를 내려받아야 한다(src\\우리_낙찰.parquet).
"""

import json
import sqlite3
from collections import Counter
from datetime import date
from pathlib import Path

from market import load_trade_index, market_for, umd_by_sgg
from paths import INSTRUCTOR_DB, LAB_DIR, OURS_PARQUET, SGG_JSON
from table import (
    Geo,
    apply_filters,
    code_pairs_instructor,
    group_instructor,
    instructor_row,
    merge,
    ours_row,
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


def add_market(rows: list[dict], index) -> Counter:
    """각 행에 당시 시세를 붙인다. 못 붙인 이유를 센다."""
    why: Counter = Counter()
    for r in rows:
        r["market_price_krw"] = None
        r["market_level"] = None
        r["market_n"] = None
        r["market_ratio"] = None  # 시세 ÷ 감정가 × 100
        r["appraisal_over_market"] = None  # 감정가 ÷ 시세
        r["win_over_market"] = None  # 낙찰가 ÷ 시세 (낙찰 건만)
        r["sale_month"] = f"{r['sale_date']:%Y-%m}"
        if r["category"] not in ("아파트", "빌라", "오피스텔"):
            why["종류에 시세 없음"] += 1
            continue
        m = market_for(
            index,
            category=r["category"],
            sgg=r["sgg"],
            umd=r["umd"],
            jibun=r["jibun"],
            bldg_name=r["bldg_name"],
            area_m2=r["area_m2"],
            sale_date=r["sale_date"],
        )
        if m is None:
            why["비교 거래 없음"] += 1
            continue
        r["market_price_krw"] = m.price_krw
        r["market_level"] = m.level
        r["market_n"] = m.n
        r["market_ratio"] = round(m.price_krw * 100 / r["appraisal_krw"], 2)
        r["appraisal_over_market"] = round(r["appraisal_krw"] / m.price_krw, 4)
        if r["winning_bid_krw"]:
            r["win_over_market"] = round(r["winning_bid_krw"] / m.price_krw, 4)
        why["붙음"] += 1
    return why


def build(out_dir: Path = LAB_DIR, today: date | None = None) -> dict:
    import pandas as pd

    today = today or date.today()
    raw = read_instructor()
    grouped, conflicts = group_instructor(raw)
    code_map = code_majority(code_pairs_instructor(raw))
    geo = geo_table()
    court = [instructor_row(g, geo, code_map) for g in grouped]
    ours = [ours_row(r, code_map) for r in read_ours()]
    merged, overlap = merge(court, ours)
    kept, dropped = apply_filters(merged)

    sgg_codes = {r["sgg"] for r in kept if r["sgg"]}
    index = load_trade_index(sgg_codes, MARKET_YEARS)
    market_why = add_market(kept, index)

    df = pd.DataFrame(kept).sort_values(["sale_date", "court_code", "case_no", "item_no"])
    out = out_dir / f"table_{today:%Y%m%d}.parquet"
    out_dir.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out, index=False)

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
            }
            for c in ("아파트", "빌라", "오피스텔")
        },
        "date_range": [f"{df['sale_date'].min()}", f"{df['sale_date'].max()}"],
    }
    (out_dir / f"table_{today:%Y%m%d}_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    return summary


if __name__ == "__main__":
    s = build()
    print(json.dumps(s, ensure_ascii=False, indent=2, default=str))
