"""추천 점수를 미리 매겨 둠(11/14 대표님 「기본 기능을 단단하게」): analysis.pick_scores 를 다시 채움.

예전에는 홈을 열 때마다 API 가 물건 4,000줄을 받아 그 자리에서 점수를 매겼음(기억해 둔 것이 없으면 10초쯤,
지역을 안 고른 손님은 4,000줄이 닷새치라 추천 범위 14일도 다 못 봄). 점수는 분석 결과에서 나오고 그날은
누구에게나 같으므로, 분석이 끝날 때마다 여기서 한 번 매겨 두고 홈은 읽기만 함.
점수(PICK-01) · 유찰 예상(WAIT-01)은 규칙 한 곳 — API 의 「그때 셈」과 같은 함수를 부름.

    uv run python -m aucs_workers.jobs.pick_scores
"""

import json
from datetime import date, timedelta
from typing import Any

import psycopg
from aucs_rules.collect import collect_row
from aucs_rules.find_filter import (
    ANALYSIS_JOIN,
    COURT_VISIBLE,
    HAS_PHOTO,
    PICK_ANALYSIS_SQL,
    RENT_JOIN,
    STATION_JOIN,
)
from aucs_rules.pick import SCORE_PURPOSES, score_row
from aucs_rules.wait import FAIL_STATS_SQL, LOOKBACK_DAYS, fold_stats, next_round
from psycopg.rows import dict_row

from aucs_workers.db import connect

# 홈에 뜰 수 있는 물건 전부: 손님에게 보이는 물건(FIND-03) 가운데 사진이 있는 것
SQL = f"""
select i.item_id, c.court_code, i.usage_name, i.appraisal_krw, i.min_price_krw, i.failed_count,
       i.building_area_m2, i.is_share, i.is_special_case, i.sale_date, i.status_code,
       {PICK_ANALYSIS_SQL} as analysis, rl.monthly_krw as rent_monthly, rl.deposit_krw as rent_deposit
from core.items i
join core.cases c using (case_id)
{RENT_JOIN}{ANALYSIS_JOIN}
where {COURT_VISIBLE} and {HAS_PHOTO}
"""
# 모아 보기(COLLECT-01)는 사진이 없어도 듦 — 손님에게 보이는 물건 전부 + 가까운 역(직선 500m 안)
COLLECT_SQL = f"""
select i.item_id, c.court_code, i.usage_name, i.appraisal_krw, i.min_price_krw, i.failed_count,
       i.is_share, i.is_special_case, i.sale_date, i.status_code,
       {PICK_ANALYSIS_SQL} as analysis, stn.station_name, stn.station_m
from core.items i
join core.cases c using (case_id)
{STATION_JOIN}{ANALYSIS_JOIN}
where {COURT_VISIBLE}
"""
COLLECT_COLS = ("key", "item_id", "why", "sort")
COLS = ("purpose", "item_id", "score", "reasons", "likely_fail", "fail_odds", "next_min_krw")


def build(
    rows: list[dict[str, Any]], stats: Any, reduction: dict[str, Any], today: date
) -> list[tuple[Any, ...]]:
    """물건 줄 → 표에 넣을 줄(목적마다 한 줄, 걸러진 물건은 뺌). DB 없이 시험할 수 있게 따로 둠."""
    out: list[tuple[Any, ...]] = []
    for r in rows:
        nr = next_round(r, stats, reduction, today)
        odds = json.dumps(nr["fail_odds"], ensure_ascii=False) if nr["fail_odds"] else None
        for purpose in SCORE_PURPOSES:
            # 월세 가운데값은 임대 목적에만 넣음(그때 셈과 같게)
            row = r if purpose == "rent" else {**r, "rent_monthly": None, "rent_deposit": None}
            p = score_row(row, purpose, today)
            if p["excluded"]:
                continue
            out.append(
                (
                    purpose or "",
                    r["item_id"],
                    int(p["score"]),
                    json.dumps(p["reasons"], ensure_ascii=False),
                    nr["likely_fail"],
                    odds,
                    nr.get("next_min_krw"),
                )  # fmt: skip
            )
    return out


def build_collections(
    rows: list[dict[str, Any]], stats: Any, reduction: dict[str, Any], today: date
) -> list[tuple[Any, ...]]:
    """물건 줄 → 모음 표에 넣을 줄(드는 모음마다 한 줄)."""
    out: list[tuple[Any, ...]] = []
    for r in rows:
        got = collect_row(r, next_round(r, stats, reduction, today), today)
        out += [(k, r["item_id"], v["reason"], float(v["sort"])) for k, v in got.items()]
    return out


def _has(cur: Any, table: str) -> bool:
    row = cur.execute("select to_regclass(%s) is not null as ok", (table,)).fetchone()
    return bool(row and row["ok"])


def _fill(cur: Any, table: str, cols: tuple[str, ...], rows: list[tuple[Any, ...]]) -> None:
    """비우고 채우기를 한 묶음으로 — 화면이 빈 표를 보는 때가 없게(다시 만들 수 있는 표)."""
    cur.execute(f"delete from {table}")
    with cur.copy(f"copy {table} ({', '.join(cols)}) from stdin") as cp:
        for x in rows:
            cp.write_row(x)


def refresh(conn: psycopg.Connection, today: date) -> int:
    """추천 점수 표 · 모음 표를 다시 채우고 넣은 줄 수를 돌려줌. 표가 없으면(이주 0052 · 0053 전) 그 표는 건너뜀."""
    cur = conn.cursor(row_factory=dict_row)
    picks, colls = _has(cur, "analysis.pick_scores"), _has(cur, "analysis.collection_items")
    if not picks and not colls:
        return 0
    stats = fold_stats(
        cur.execute(FAIL_STATS_SQL, (today - timedelta(days=LOOKBACK_DAYS), today)).fetchall()
    )
    red = cur.execute(
        "select value from ref.rule_tables where rule_key = 'court_reduction_pct'"
        " and valid_from <= %s order by valid_from desc limit 1",
        (today,),
    ).fetchone()
    reduction = dict((red or {}).get("value") or {})
    n = 0
    if picks:
        out = build(cur.execute(SQL, {"today": today}).fetchall(), stats, reduction, today)
        _fill(cur, "analysis.pick_scores", COLS, out)
        conn.commit()
        n += len(out)
    if colls:
        out = build_collections(
            cur.execute(COLLECT_SQL, {"today": today}).fetchall(), stats, reduction, today
        )
        _fill(cur, "analysis.collection_items", COLLECT_COLS, out)
        conn.commit()
        n += len(out)
    return n


def main() -> None:
    with connect() as conn:
        n = refresh(conn, date.today())
    print(f"추천 점수 · 모음 {n:,}줄")


if __name__ == "__main__":
    main()
