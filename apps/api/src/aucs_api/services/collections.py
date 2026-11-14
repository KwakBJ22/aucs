"""모아 보기(11/7 대표님 — 차별화 · 손님에게 쓸모 있는 것만).

모음 판단은 규칙 COLLECT-01(packages/rules/collect.py) 하나, 「기다리면 더 싸질 물건」은 홈 추천과 같은
규칙(실제 유찰 비율, WAIT-01). 내 지역·현금 조건을 받으면 그 안에서만.
11/14: 수집기(jobs/pick_scores)가 분석 뒤마다 물건을 모음에 미리 나눠 둠(analysis.collection_items) — 여기서는 읽기만.
예전엔 열 때마다 물건 2만 줄을 받아 그 자리에서 나눴음. 표가 없거나 오래됐으면 예전처럼 그때 셈.
"""

from datetime import date, datetime, timedelta
from typing import Any

import psycopg
from aucs_rules.collect import KEYS, collect_row
from aucs_rules.find_filter import ANALYSIS_JOIN, COURT_VISIBLE, STATION_JOIN, court_where
from aucs_rules.pick import diversify

from aucs_api.db import batch, connect
from aucs_api.services.items import _CARD_SQL, add_cols, add_join, attach_stations, card
from aucs_api.services.picks import _SQL, light_card, mark_next_round, reduction_table

_JOIN_CI = (
    "join core.cases c using (case_id)\njoin analysis.collection_items ci on ci.item_id = i.item_id"
)
# 미리 나눠 둔 것에서: 먼저 가벼운 줄(모음 · 순서 값 · 추리는 데 쓰는 칸)만 모두 받아 건수를 세고 나갈 물건을 고른 뒤,
# 고른 물건만 카드 칸을 받음(11/14 — 모음마다 카드 칸까지 받으면 분석 글을 물건마다 풀어 몇 초가 걸림)
_LIGHT_SQL = f"""
select ci.key, ci.sort, i.item_id, i.sale_date, c.court_code, c.case_no, i.sigungu, i.gu, i.building_desc
from core.items i
{_JOIN_CI}
{ANALYSIS_JOIN}
where {COURT_VISIBLE}"""
_ITEMS_SQL = add_cols(_CARD_SQL, "i.is_special_case, i.status_code, ci.key, ci.why").replace(
    "join core.cases c using (case_id)", _JOIN_CI, 1
)
_FRESH_HOURS = 36  # 이보다 오래됐으면 안 씀(수집기가 멈춘 것) → 그때 셈


def _from_table(
    more: str, params: dict[str, Any], key: str | None, limit: int, today: date
) -> dict[str, Any] | None:
    """미리 나눠 둔 표로 답함. 표가 없거나 비었거나 오래됐으면 None."""
    try:
        with connect() as c:
            q_at, q_rows = batch(
                c,
                [
                    ("select max(computed_at) as at from analysis.collection_items", None),
                    (_LIGHT_SQL + more + " order by ci.sort desc, i.item_id", params),
                ],
            )
            at = (q_at.fetchone() or {}).get("at")
            if not at or datetime.now(at.tzinfo) - at > timedelta(hours=_FRESH_HOURS):
                return None
            groups: dict[str, list[dict[str, Any]]] = {k: [] for k in KEYS}
            for r in q_rows.fetchall():
                if r["key"] in groups:
                    groups[r["key"]].append(light_card(r, today))
            chosen: dict[str, list[dict[str, Any]]] = {}
            for k in KEYS:
                if key and k != key:
                    chosen[k] = []
                else:
                    chosen[k] = groups[k][:limit] if key else diversify(groups[k], limit)
            ids = sorted({x["item_id"] for v in chosen.values() for x in v})
            rows = (
                c.execute(
                    _ITEMS_SQL + " and i.item_id = any(%(ids)s)", {**params, "ids": ids}
                ).fetchall()
                if ids
                else []
            )
            reduction = reduction_table(today)
            cards: dict[tuple[str, str], dict[str, Any]] = {}
            for r in rows:
                cd = card(r, today)
                mark_next_round(cd, r, reduction, today)
                cards[(r["key"], r["item_id"])] = {**cd, "why": r["why"]}
            out: dict[str, Any] = {}
            for k in KEYS:
                items = [cards[(k, x["item_id"])] for x in chosen[k] if (k, x["item_id"]) in cards]
                out[k] = {"total": len(groups[k]), "items": items}
            # 카드의 「○○역 도보 약 N분」은 다른 목록과 같은 길로, 나갈 카드에만 한 번에
            attach_stations(c, [x for v in out.values() for x in v["items"]])
    except psycopg.Error:  # 표가 아직 없음(이주 0053 전) 등
        return None
    return out


def collections(
    *,
    sigungu: list[str],
    max_cash: int | None,
    key: str | None,
    limit: int,
    today: date,
    homes: int = 0,
) -> dict[str, Any]:
    """모음마다 건수는 늘 주고, 물건은 key 가 없으면 모음마다 앞 몇 건(같은 단지 1·같은 구 2건까지),
    있으면 그 모음만 limit 건 — 화면이 건수와 목록을 한 번에 받게(11/7)."""
    params: dict[str, Any] = {"today": today}
    more, fp = court_where(
        {"sigungu": sigungu, "max_cash": max_cash, "homes": homes}, today
    )  # 찾기와 같은 규칙(FIND-03)
    params.update(fp)
    got_table = _from_table(more, params, key, limit, today)
    if got_table is not None:
        return got_table

    # ── 그때 셈(미리 나눠 둔 것이 없을 때만)
    sql = add_join(add_cols(_SQL, "stn.station_name, stn.station_m"), STATION_JOIN)
    sql += more
    sql += " order by i.sale_date limit 20000"  # 전체 지역도 빠짐없이(11/7 — 6000 이면 먼 날 물건이 빠졌음)
    with connect() as c:
        rows = c.execute(sql, params).fetchall()
    reduction = reduction_table(today)

    groups: dict[str, list[dict[str, Any]]] = {k: [] for k in KEYS}
    for r in rows:
        cd = card(r, today)
        mark_next_round(cd, r, reduction, today)
        got = collect_row(r, cd, today)  # 다음 회차 · 유찰 예상 표시는 카드에 방금 붙인 것
        for k, v in got.items():
            groups[k].append({**cd, "why": v["reason"], "_sort": v["sort"]})

    out: dict[str, Any] = {}
    for k in KEYS:
        rows_k = groups[k]
        if key and k != key:
            out[k] = {"total": len(rows_k), "items": []}
            continue
        rows_k = sorted(rows_k, key=lambda x: -x["_sort"])
        out[k] = {
            "total": len(rows_k),
            "items": rows_k[:limit] if key else diversify(rows_k, limit),
        }
        for x in out[k]["items"]:
            x.pop("_sort", None)
    return out
