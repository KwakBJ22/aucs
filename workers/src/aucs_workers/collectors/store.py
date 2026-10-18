"""원본은 raw에 추가만, 정리본은 core에 넣거나 고칩니다."""

from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from aucs_workers.collectors.parse import checksum, parse_item, parse_result, to_date


def save_raw(conn: psycopg.Connection, table: str, court: str, rows: list[dict[str, Any]]) -> int:
    """같은 내용(같은 checksum)은 다시 넣지 않습니다."""
    n = 0
    with conn.cursor() as cur:
        for r in rows:
            cur.execute(
                f"insert into raw.{table} (court_code, doc_key, sale_date, payload, checksum) "
                "values (%s,%s,%s,%s,%s) on conflict do nothing",
                (court, r.get("docid") or "", to_date(r.get("maeGiil")), Jsonb(r), checksum(r)),
            )
            n += cur.rowcount
    return n


_CASE = """insert into core.cases (case_id, court_code, case_no, dept_name)
values (%(case_id)s, %(court_code)s, %(case_no)s, %(dept_name)s)
on conflict (case_id) do update set dept_name = excluded.dept_name, updated_at = now()"""

_ITEM_COLS = [
    "item_id", "case_id", "item_no", "doc_key", "usage_name", "usage_code", "address", "region_code",
    "sido", "sigungu", "gu", "lot_no", "building_desc", "building_area_m2", "appraisal_krw",
    "min_price_krw", "failed_count", "sale_date", "sale_place", "status_code", "note_masked", "is_share",
]  # fmt: skip
_ITEM = (
    f"insert into core.items ({', '.join(_ITEM_COLS)}, geom, fetched_at, checked_at) values ("
    + ", ".join(f"%({c})s" for c in _ITEM_COLS)
    + ", case when %(lon)s::float is null then null else "
    "st_setsrid(st_makepoint(%(lon)s::float, %(lat)s::float), 4326)::geography end, now(), now())"
    " on conflict (item_id) do update set "
    + ", ".join(f"{c} = excluded.{c}" for c in _ITEM_COLS[3:])
    + ", geom = excluded.geom, fetched_at = now(), checked_at = now()"
    # 내용이 실제로 바뀐 때만 updated_at 을 올림 → 아침 분석(--stale)이 바뀐 물건만 다시 계산
    + ", updated_at = case when ("
    + ", ".join(f"core.items.{c}" for c in _ITEM_COLS[3:])
    + ") is distinct from ("
    + ", ".join(f"excluded.{c}" for c in _ITEM_COLS[3:])
    + ") then now() else core.items.updated_at end"
)

_ROUND = """insert into core.rounds (round_id, item_id, sale_date, appraisal_krw, min_price_krw,
  failed_count, sale_place, fetched_at, checked_at)
values (%(round_id)s, %(item_id)s, %(sale_date)s, %(appraisal_krw)s, %(min_price_krw)s,
  %(failed_count)s, %(sale_place)s, now(), now())
on conflict (round_id) do update set min_price_krw = excluded.min_price_krw,
  failed_count = excluded.failed_count, sale_place = excluded.sale_place, checked_at = now()"""

# 더 뒤 기일이 새로 나오면 앞 기일은 끝난 것: 최저가가 내려갔으면 유찰, 아니면 변경·연기
_CLOSE_EARLIER = """update core.rounds o set result = case when o.min_price_krw > n.min_price_krw
  then 'failed' else 'changed' end
from core.rounds n
where n.round_id = %(round_id)s and o.item_id = n.item_id and o.sale_date < n.sale_date
  and o.result = 'scheduled'"""


def save_items(conn: psycopg.Connection, rows: list[dict[str, Any]]) -> int:
    with conn.cursor() as cur:
        for r in rows:
            p = parse_item(r)
            cur.execute(_CASE, p["case"])
            cur.execute(_ITEM, p["item"])
            if p["round"]:
                cur.execute(_ROUND, p["round"])
                cur.execute(_CLOSE_EARLIER, p["round"])
    return len(rows)


_RESULT_COLS = [
    "court_code", "case_no", "item_no", "sale_date", "item_id", "usage_name", "address", "sido",
    "region_code", "building_area_m2", "appraisal_krw", "min_price_krw", "winning_bid_krw",
    "sale_rate", "failed_count", "result", "is_share",
]  # fmt: skip
_RESULT = (
    f"insert into core.sale_results ({', '.join(_RESULT_COLS)}, origin, fetched_at) values ("
    + ", ".join(f"%({c})s" for c in _RESULT_COLS)
    + ", 'court_collect', now()) on conflict (court_code, case_no, item_no, sale_date) do update set "
    + ", ".join(f"{c} = excluded.{c}" for c in _RESULT_COLS[4:])
    + ", origin = 'court_collect', fetched_at = now()"
)
_ROUND_RESULT = """update core.rounds set result = %(result)s, checked_at = now()
where item_id = %(item_id)s and sale_date = %(sale_date)s"""


def save_results(conn: psycopg.Connection, rows: list[dict[str, Any]]) -> int:
    n = 0
    with conn.cursor() as cur:
        for r in rows:
            p = parse_result(r)
            if p is None:
                continue
            cur.execute(_RESULT, p)
            cur.execute(_ROUND_RESULT, p)
            n += 1
    return n
