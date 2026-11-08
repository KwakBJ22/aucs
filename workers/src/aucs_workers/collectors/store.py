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
    "region_code_court",
]  # fmt: skip
# 법원 지역 코드는 옛 코드가 섞여 있음 → 원래 값은 region_code_court 에 두고,
# region_code 는 DB 함수가 주소의 동 이름으로 바로잡은 값 (0022)
_VALUE = {"region_code": "ref.region_code_for(%(region_code_court)s, %(address)s)"}
# 물건은 좌표가 있어 동 이름이 여러 구에 있거나 없을 때 좌표로 가려냄 (0023)
_ITEM_VALUE = {
    "region_code": "ref.region_code_for(%(region_code_court)s, %(address)s, %(lon)s::float, %(lat)s::float)"
}


def _val(c: str, extra: dict[str, str] | None = None) -> str:
    return (extra or {}).get(c) or _VALUE.get(c, f"%({c})s")


_ITEM = (
    f"insert into core.items ({', '.join(_ITEM_COLS)}, geom, fetched_at, checked_at) values ("
    + ", ".join(_val(c, _ITEM_VALUE) for c in _ITEM_COLS)
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


# 유찰 횟수 바로잡기(11/9): 법원 목록 숫자가 실제보다 적은 물건이 있음(서울중앙, 1회씩).
# 유찰 기록 수가 더 크고 최저가 비율(법원 저감률로 거꾸로 센 횟수)과 맞을 때만 기록 수로.
_FIX_FAILED = """with red as (
  select (value -> split_part(%(item_id)s, '-', 1) ->> 'pct')::numeric as pct
  from ref.rule_tables where rule_key = 'court_reduction_pct' and valid_from <= current_date
  order by valid_from desc limit 1),
f as (
  select count(distinct r.sale_date)::int as n
  from core.rounds r join core.items i using (item_id)
  where r.item_id = %(item_id)s and r.result = 'failed' and r.sale_date < i.sale_date)
update core.items i set failed_count = f.n, updated_at = now()
from f, red
where i.item_id = %(item_id)s and f.n > coalesce(i.failed_count, 0) and red.pct is not null
  and i.min_price_krw > 0 and i.min_price_krw < i.appraisal_krw
  and round(ln(i.min_price_krw::numeric / i.appraisal_krw) / ln(1 - red.pct / 100)) = f.n"""


def fix_failed_count(cur: Any, item_id: str) -> None:
    cur.execute(_FIX_FAILED, {"item_id": item_id})


def save_items(conn: psycopg.Connection, rows: list[dict[str, Any]]) -> int:
    with conn.cursor() as cur:
        for r in rows:
            p = parse_item(r)
            cur.execute(_CASE, p["case"])
            cur.execute(_ITEM, p["item"])
            if p["round"]:
                cur.execute(_ROUND, p["round"])
                cur.execute(_CLOSE_EARLIER, p["round"])
                fix_failed_count(cur, p["round"]["item_id"])
    return len(rows)


_RESULT_COLS = [
    "court_code", "case_no", "item_no", "sale_date", "item_id", "usage_name", "address", "sido",
    "region_code", "building_area_m2", "appraisal_krw", "min_price_krw", "winning_bid_krw",
    "sale_rate", "failed_count", "result", "is_share", "region_code_court",
]  # fmt: skip
_RESULT = (
    f"insert into core.sale_results ({', '.join(_RESULT_COLS)}, origin, fetched_at) values ("
    + ", ".join(_val(c) for c in _RESULT_COLS)
    + ", 'court_collect', now()) on conflict (court_code, case_no, item_no, sale_date) do update set "
    + ", ".join(f"{c} = excluded.{c}" for c in _RESULT_COLS[4:])
    + ", origin = 'court_collect', fetched_at = now()"
)
# 결과를 회차에도: 없던 회차(우리 목록에 늦게 들어온 물건)는 새로 넣음(11/8 — 예전엔 있는 회차만 고쳐
# 유찰 기록이 비었음). 우리 목록에 없는 물건은 건너뜀.
_ROUND_RESULT = """insert into core.rounds (round_id, item_id, sale_date, appraisal_krw, min_price_krw,
  failed_count, result, fetched_at, checked_at)
select %(item_id)s || '-' || to_char(%(sale_date)s::date, 'YYYYMMDD'), i.item_id, %(sale_date)s,
  %(appraisal_krw)s, %(min_price_krw)s, %(failed_count)s, %(result)s, now(), now()
from core.items i where i.item_id = %(item_id)s
on conflict (round_id) do update set result = excluded.result, checked_at = now(),
  min_price_krw = coalesce(core.rounds.min_price_krw, excluded.min_price_krw)"""


def save_results(conn: psycopg.Connection, rows: list[dict[str, Any]]) -> int:
    n = 0
    with conn.cursor() as cur:
        for r in rows:
            p = parse_result(r)
            if p is None:
                continue
            cur.execute(_RESULT, p)
            cur.execute(_ROUND_RESULT, p)
            if p.get("item_id"):
                fix_failed_count(cur, p["item_id"])
            n += 1
    return n
