"""자료 점검(11/24 대표님 「빠뜨리지 않게」 ③) — 아침 분석 뒤 하루 한 번, 틀린 · 빠진 정보를 셉니다.

11/24 물건 검증(서울동부 2024타경57221 → 진행 물건 전체 맞대기)에서 나온 틀림 꼴을 날마다 다시 셈:
  list_diff   법원 목록 원문(최저가 notifyMinmaePrice1 · 감정가 · 매각기일)과 우리 물건이 다름
  note_signal 비고 글(농취증 · 재매각 · 유치권 · 법정지상권 · 대항력 있는 임차인 · 보증기관 대항력 포기)에 있는데 신호가 없음
  soon_docs   입찰 7일 안인데 물건상세 · 문건송달 · 현황조사가 비었거나 묵음(입찰 임박 서류 대상, 최대 300)
  stale       진행 물건 중 지금 규칙 버전으로 분석되지 않은 것
  empty_detail 하루 안에 넣은 빈 서류(물건상세 dma_result 없음 · 현황조사 · 문건송달 · 기일 · 사건정보 {"ipcheck"}뿐)
              — 11/25 수원 2025타경55353 · 상세 값 점검: 빈 답이 최근 것이 돼 명세서 · 문건 흐름을 못 읽었음
  unit_area   진행 물건 중 대장 호 전유 면적이 법원 면적의 1.5배 넘게 다른 것 — 11/25: 다른 동 · 대장 두 장을 더했음
  over_market 진행 물건 중 예상 낙찰가(감정가 × 가운데 낙찰가율)가 시세보다 10% 넘게 높은 것 — 11/26 타워팰리스:
              입찰 전 값으로 되짚으면 이런 물건 41건 중 20건이 예상보다 낮게 팔림(범위 안 32%, 나머지 41%)
결과는 ops.job_runs.message(JSON)에 — 빨간 불 판단은 ops_watch.red_lights 한 곳(LIMITS 넘으면).

    uv run python -m aucs_workers.jobs.data_check
"""

import json
from datetime import date
from typing import Any

import psycopg
from aucs_rules import ENGINE_VERSION
from aucs_rules.find_filter import VEHICLES
from aucs_rules.spec_facts import note_facts

from aucs_workers.db import connect
from aucs_workers.jobs.runlog import run

REAL_ESTATE = f"coalesce(i.usage_name, '') !~ '{VEHICLES}'"  # court_docs 와 같은 뜻
AREA = "i.sido in ('서울특별시', '경기도', '인천광역시')"
LIVE = f"{AREA} and i.sale_date >= current_date and i.status_code is distinct from 'gone'"

LIST_DIFF_SQL = """
with r as (
  select distinct on (court_code, payload->>'srnSaNo', payload->>'maemulSer')
         court_code || '-' || (payload->>'srnSaNo') || '-' || (payload->>'maemulSer') as item_id, payload as p
  from raw.court_item_raw
  where source_id = 'court_items' and payload->>'hjguSido' in ('서울특별시', '경기도', '인천광역시')
    and to_date(payload->>'maeGiil', 'YYYYMMDD') >= current_date
  order by court_code, payload->>'srnSaNo', payload->>'maemulSer', fetched_at desc)
select i.item_id from r join core.items i using (item_id)
where i.min_price_krw is distinct from nullif(p->>'notifyMinmaePrice1', '0')::bigint
   or i.appraisal_krw is distinct from (p->>'gamevalAmt')::bigint
   or i.sale_date is distinct from to_date(p->>'maeGiil', 'YYYYMMDD')
"""

NOTE_SQL = f"""
select i.item_id, i.note_masked,
       (select coalesce(array_agg(s->>'rule_id'), '{{}}') from jsonb_array_elements(a.result->'signals') s) as rules
from core.items i
join lateral (select result from analysis.item_analysis a where a.item_id = i.item_id
              order by version desc limit 1) a on true
where {LIVE} and i.note_masked is not null and i.note_masked <> ''
"""

STALE_SQL = f"""
select i.item_id from core.items i
left join lateral (select engine_version from analysis.item_analysis a where a.item_id = i.item_id
                   order by version desc limit 1) a on true
where {LIVE} and {REAL_ESTATE} and a.engine_version is distinct from %s
"""

EMPTY_DETAIL_SQL = """
select r.case_id || ' ' || r.doc_kind from raw.court_doc_raw r
where r.fetched_at > now() - interval '1 day'
  and ((r.doc_kind like 'item_detail_%%' and jsonb_typeof(r.payload->'dma_result') is distinct from 'object')
       or (r.doc_kind in ('status_report','deliveries','schedule','case_info')
           and not exists (select 1 from jsonb_object_keys(r.payload) k where k <> 'ipcheck')))
"""

UNIT_AREA_SQL = """
select i.item_id from core.items i join core.building_units u using (item_id)
where i.sale_date >= current_date and u.result = 'ok' and i.building_area_m2 > 0 and u.own_area > 0
  and greatest(u.own_area, i.building_area_m2) > 1.5 * least(u.own_area, i.building_area_m2)
"""

OVER_MARKET_SQL = """
select i.item_id from core.items i
cross join lateral (select result from analysis.item_analysis a where a.item_id = i.item_id order by version desc limit 1) r
where i.sale_date >= current_date and i.status_code is distinct from 'gone' and i.appraisal_krw > 0
  and (r.result -> 'market' ->> 'price_krw') is not null and (r.result -> 'sale_rate' ->> 'p50') is not null
  and i.appraisal_krw * (r.result -> 'sale_rate' ->> 'p50')::numeric / 100 > 1.1 * (r.result -> 'market' ->> 'price_krw')::numeric
"""

# 비고 사실 → 신호
NOTE_RULE = {
    "lien_reported": "risk.lien",
    "statutory_superficies": "risk.superficies",
    "farmland_permit": "risk.farmland",
    "resale": "risk.resale",
    "senior_tenant_assumed": "risk.senior_tenant",
    "lease_reg_released": "risk.lease_reg_released",
}


def note_misses(rows: list[tuple[str, str, list[str]]]) -> list[str]:
    """비고 글로 보면 있어야 할 신호가 없는 물건(순수 함수)."""
    out = []
    for item_id, note, rules in rows:
        have = set(rules or [])
        # 명세서에 인수 권리가 있으면 말소동의로 보지 않음(analyze 와 같게)
        ctx = {"prior_assumed_rights": True} if "risk.prior_rights" in have else {}
        for k in note_facts(note, ctx):
            if k in NOTE_RULE and NOTE_RULE[k] not in have:  # 신호가 없는 덧붙임 사실(…_by)은 건너뜀
                out.append(item_id)
                break
    return out


def check(conn: psycopg.Connection, today: date) -> dict[str, Any]:
    from aucs_workers.collectors.court_docs import soon_targets

    cur = conn.cursor()
    found: dict[str, list[str]] = {
        "list_diff": [r[0] for r in cur.execute(LIST_DIFF_SQL).fetchall()],
        "note_signal": note_misses(cur.execute(NOTE_SQL).fetchall()),
        "soon_docs": [f"{c}-{n}" for c, n in soon_targets(conn, today)],
        "stale": [r[0] for r in cur.execute(STALE_SQL, (ENGINE_VERSION,)).fetchall()],
        "empty_detail": [r[0] for r in cur.execute(EMPTY_DETAIL_SQL).fetchall()],
        "unit_area": [r[0] for r in cur.execute(UNIT_AREA_SQL).fetchall()],
        "over_market": [r[0] for r in cur.execute(OVER_MARKET_SQL).fetchall()],
    }
    return {k: {"n": len(v), "ex": v[:5]} for k, v in found.items()} | {"engine": ENGINE_VERSION}


def main() -> None:
    with connect() as conn, run(conn, "data_check", "자료 점검") as job:
        res = check(conn, date.today())
        job.count = sum(v["n"] for v in res.values() if isinstance(v, dict))
        conn.execute(
            "update ops.job_runs set message = %s where run_id = %s",
            (json.dumps(res, ensure_ascii=False), job.run_id),
        )
        conn.commit()
        for k, v in res.items():
            print(k, v)


if __name__ == "__main__":
    main()
