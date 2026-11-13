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
from aucs_rules.find_filter import (
    ANALYSIS_JOIN,
    COURT_VISIBLE,
    HAS_PHOTO,
    PICK_ANALYSIS_SQL,
    RENT_JOIN,
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


def refresh(conn: psycopg.Connection, today: date) -> int:
    """표를 다시 채우고 넣은 줄 수를 돌려줌. 표가 없으면(이주 0052 전) 0 — 부르는 쪽은 멈추지 않음."""
    cur = conn.cursor(row_factory=dict_row)
    ok = cur.execute("select to_regclass('analysis.pick_scores') is not null as ok").fetchone()
    if not ok or not ok["ok"]:
        return 0
    stats = fold_stats(
        cur.execute(FAIL_STATS_SQL, (today - timedelta(days=LOOKBACK_DAYS), today)).fetchall()
    )
    red = cur.execute(
        "select value from ref.rule_tables where rule_key = 'court_reduction_pct'"
        " and valid_from <= %s order by valid_from desc limit 1",
        (today,),
    ).fetchone()
    rows = cur.execute(SQL, {"today": today}).fetchall()
    out = build(rows, stats, dict((red or {}).get("value") or {}), today)
    # 비우고 채우기를 한 묶음으로 — 홈이 빈 표를 보는 때가 없게
    cur.execute("delete from analysis.pick_scores")
    with cur.copy(f"copy analysis.pick_scores ({', '.join(COLS)}) from stdin") as cp:
        for x in out:
            cp.write_row(x)
    conn.commit()
    return len(out)


def main() -> None:
    with connect() as conn:
        n = refresh(conn, date.today())
    print(f"추천 점수 {n:,}줄")


if __name__ == "__main__":
    main()
