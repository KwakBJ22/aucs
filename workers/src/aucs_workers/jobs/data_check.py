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
11/27 물건 검증 2(메인 · 역세권 10건)에서 나온 꼴 — 사람이 표본을 보기 전에 전체에서 먼저 셈:
  tenant_dup   같은 물건에 보증금 · 전입일이 같은 임차인 줄이 둘 이상(보증기관 줄 빼고) — 한 사람을 두 번 셈
  tenant_name  명세서 원본 임차인 이름이 비었거나 보증기관 이름 조각(「…한국주」 · 「공사(…)」)으로 갈라짐
  tenant_date  임차인 날짜가 말이 안 됨(확정일이 전입보다 5년 넘게 앞섬 · 앞으로의 날 · 1980년 전)
  deposit_big  임차인 보증금 합이 감정가의 1.5배 넘음(같은 보증금을 여러 번 더했거나 잘못 읽음)
  market_odd   시세가 감정가의 절반 아래 · 두 배 위(다른 집 거래를 잡았을 수 있음)
  prior_release 「소멸되지 않는 권리」 칸에 말소 동의 글이 있는데 「인수」 신호가 남음
  doc_late     분석 뒤 6시간 넘게 지나 새 서류를 받았는데 다시 분석 안 됨
  golden       사람이 원문과 맞대 본 물건(golden_items.json)의 정답과 지금 분석이 다름 — 고친 것이 다른 곳을 망가뜨림
  changes      하루 안에 다시 분석된 물건 중 신호 · 임차인 수가 바뀐 것(빨간 불 아님 — 규칙을 고친 효과를 건수로)
결과는 ops.job_runs.message(JSON)에 — 빨간 불 판단은 ops_watch.red_lights 한 곳(LIMITS 넘으면).

    uv run python -m aucs_workers.jobs.data_check
"""

import json
from collections import Counter
from datetime import date
from pathlib import Path
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

# ── 11/27 물건 검증 2 ─────────────────────────────────────────────────────────
_LIVE_T = f"""
with live as (select i.* from core.items i where {LIVE}),
t as (select l.item_id, t.tenant_id, t.name_raw, t.move_in_date, t.fixed_date, t.claim_date, t.deposit_krw, t.source
      from live l join core.tenants t on t.case_id = l.case_id and (t.item_id is null or t.item_id = l.item_id))
"""
_GUAR = r"보증공사|보증보험|주택금융|도시보증|주택도|\(임차인"
TENANT_DUP_SQL = _LIVE_T + f"""
select distinct a.item_id from t a join t b on a.item_id = b.item_id and a.tenant_id < b.tenant_id
  and a.deposit_krw = b.deposit_krw and a.move_in_date is not distinct from b.move_in_date
where coalesce(a.name_raw, '') !~ '{_GUAR}' and coalesce(b.name_raw, '') !~ '{_GUAR}'
"""
TENANT_NAME_SQL = _LIVE_T + """
select distinct item_id from t where source = 'spec' and (name_raw is null
  or name_raw ~ '^(공사|시보증|택도시|도시보증|보증공사|택금융|금융공사)'
  or name_raw ~ '[가-힣]{2,4}(한국주택금융|한국주택|한국주|주택도시|주택도)$')
"""
TENANT_DATE_SQL = _LIVE_T + """
select distinct item_id from t where fixed_date < move_in_date - interval '5 years'
  or move_in_date > current_date or fixed_date > current_date or claim_date > current_date
  or move_in_date < date '1980-01-01'
"""
DEPOSIT_BIG_SQL = _LIVE_T + f"""
select l.item_id from live l join (
  select a.item_id, sum(a.deposit_krw) s from t a
  -- 보증기관 줄은 같은 보증금 · 전입의 원래 임차인 줄이 있으면 한 사람(분석의 merge_guarantor 와 같게, 11/27)
  where not (coalesce(a.name_raw, '') ~ '{_GUAR}' and exists (
    select 1 from t b where b.item_id = a.item_id and b.tenant_id <> a.tenant_id and b.deposit_krw = a.deposit_krw
      and coalesce(b.name_raw, '') !~ '{_GUAR}'))
  group by 1) x using (item_id)
where l.appraisal_krw > 0 and x.s > 1.5 * l.appraisal_krw
"""
MARKET_ODD_SQL = f"""
select i.item_id from core.items i
cross join lateral (select result from analysis.item_analysis a where a.item_id = i.item_id order by version desc limit 1) r
where {LIVE} and i.appraisal_krw > 0 and (r.result -> 'market' ->> 'price_krw') is not null
  and ((r.result -> 'market' ->> 'price_krw')::numeric < 0.5 * i.appraisal_krw
       or (r.result -> 'market' ->> 'price_krw')::numeric > 2 * i.appraisal_krw)
"""
PRIOR_RELEASE_SQL = f"""
select i.item_id from core.items i
cross join lateral (select result from analysis.item_analysis a where a.item_id = i.item_id order by version desc limit 1) r
cross join lateral (select d.payload -> 'dma_result' -> 'dspslGdsDxdyInfo' ->> 'ndstrcRghCtt' as keep from raw.court_doc_raw d
                    where d.case_id = i.case_id and d.doc_kind = 'item_detail_' || i.item_no
                      and d.payload -> 'dma_result' -> 'dspslGdsDxdyInfo' ->> 'gdsSpcfcWrtYmd' is not null
                    order by d.fetched_at desc limit 1) k
where {LIVE} and k.keep ~ '말소\s*에?\s*동의|말소\s*하는\s*(것|데)\s*에?\s*동의'
  and k.keep !~ '전세권|가등기|가처분|지역권|유치권|근저당(?!\\s*권자\\s*겸)'
  and not (k.keep ~ '지상권' and k.keep !~ '지상권\\s*자')
  and exists (select 1 from jsonb_array_elements(r.result -> 'signals') x where x ->> 'rule_id' = 'risk.prior_rights')
"""
DOC_LATE_SQL = f"""
select i.item_id from core.items i
cross join lateral (select computed_at from analysis.item_analysis a where a.item_id = i.item_id order by version desc limit 1) r
where {LIVE} and exists (select 1 from raw.court_doc_raw d where d.case_id = i.case_id
                         and d.fetched_at > r.computed_at + interval '6 hours')
"""

GOLDEN = Path(__file__).with_name("golden_items.json")
LATEST2_SQL = """
select item_id, version, result from (
  select a.item_id, a.version, a.result, row_number() over (partition by a.item_id order by a.version desc) n
  from analysis.item_analysis a where a.item_id = any(%s)) x where n <= 2 order by item_id, version desc
"""
CHANGED_IDS_SQL = f"""
select i.item_id from core.items i where {LIVE}
  and exists (select 1 from analysis.item_analysis a where a.item_id = i.item_id and a.computed_at > now() - interval '1 day')
  and (select count(*) from analysis.item_analysis a where a.item_id = i.item_id) >= 2
"""


def _rules(result: dict[str, Any] | None) -> set[str]:
    return {s.get("rule_id") for s in (result or {}).get("signals") or [] if s.get("rule_id")}


def golden_misses(expected: dict[str, dict[str, Any]], results: dict[str, dict[str, Any]]) -> list[str]:
    """정답표와 지금 분석을 맞댐(순수 함수) → 「물건 무엇이 다름」 목록. 분석이 없는 물건(끝남)은 건너뜀."""
    out = []
    for item_id, e in expected.items():
        if item_id.startswith("_") or item_id not in results:
            continue
        r = results[item_id] or {}
        rules = _rules(r)
        titles = " ".join(s.get("title") or "" for s in r.get("signals") or [])
        if "tenant_count" in e and r.get("tenant_count") != e["tenant_count"]:
            out.append(f"{item_id} 임차인 {r.get('tenant_count')}명(정답 {e['tenant_count']})")
        out += [f"{item_id} {k} 없음" for k in e.get("has", []) if k not in rules]
        out += [f"{item_id} {k} 있음" for k in e.get("not", []) if k in rules]
        out += [f"{item_id} 「{w}」" for w in e.get("title_not", []) if w in titles]
    return out


def change_summary(pairs: dict[str, tuple[dict[str, Any], dict[str, Any]]]) -> dict[str, Any]:
    """물건마다 (지금, 바로 앞) 분석 → 바뀐 신호 · 임차인 수 건수(순수 함수)."""
    added: Counter[str] = Counter()
    removed: Counter[str] = Counter()
    tenants = 0
    changed = []
    for item_id, (now, before) in pairs.items():
        a, b = _rules(now), _rules(before)
        t = (now or {}).get("tenant_count") != (before or {}).get("tenant_count")
        if a != b or t:
            changed.append(item_id)
        added.update(a - b)
        removed.update(b - a)
        tenants += t
    return {"n": len(changed), "ex": changed[:5], "added": dict(added.most_common(10)),
            "removed": dict(removed.most_common(10)), "tenant_count": tenants}  # fmt: skip


def _latest2(cur: Any, ids: list[str]) -> dict[str, list[dict[str, Any]]]:
    got: dict[str, list[dict[str, Any]]] = {}
    for k in range(0, len(ids), 2000):
        for item_id, _v, result in cur.execute(LATEST2_SQL, (ids[k : k + 2000],)).fetchall():
            got.setdefault(item_id, []).append(result)
    return got


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
        "tenant_dup": [r[0] for r in cur.execute(TENANT_DUP_SQL).fetchall()],
        "tenant_name": [r[0] for r in cur.execute(TENANT_NAME_SQL).fetchall()],
        "tenant_date": [r[0] for r in cur.execute(TENANT_DATE_SQL).fetchall()],
        "deposit_big": [r[0] for r in cur.execute(DEPOSIT_BIG_SQL).fetchall()],
        "market_odd": [r[0] for r in cur.execute(MARKET_ODD_SQL).fetchall()],
        "prior_release": [r[0] for r in cur.execute(PRIOR_RELEASE_SQL).fetchall()],
        "doc_late": [r[0] for r in cur.execute(DOC_LATE_SQL).fetchall()],
    }
    expected = json.loads(GOLDEN.read_text(encoding="utf-8"))
    g = _latest2(cur, [k for k in expected if not k.startswith("_")])
    found["golden"] = golden_misses(expected, {k: v[0] for k, v in g.items()})
    ch = _latest2(cur, [r[0] for r in cur.execute(CHANGED_IDS_SQL).fetchall()])
    changes = change_summary({k: (v[0], v[1]) for k, v in ch.items() if len(v) == 2})
    return {k: {"n": len(v), "ex": v[:5]} for k, v in found.items()} | {
        "changes": changes, "engine": ENGINE_VERSION}  # fmt: skip


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
