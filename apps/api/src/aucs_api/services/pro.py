"""PC 전문가 「전체 물건」 표: 조건 여러 개로 거르고, 고른 물건 요약·CSV.
(지금의 경매레이더 화면을 옮긴 것. 전문가 이용권 잠금은 이용권을 붙일 때.)"""

import csv
import io
from datetime import date
from typing import Any

from aucs_rules.find_filter import (
    ANALYSIS_JOIN,
    COURT_VISIBLE,
    ONBID_VISIBLE,
    USAGE_GROUPS,
    VEHICLES,
    onbid_where,
)
from aucs_rules.find_filter import court_where as build_where
from aucs_rules.progress import judge_progress

from aucs_api.db import batch, connect
from aucs_api.services.items import COURT_NAME
from aucs_api.services.onbid import KIND_KO

SORTS = {
    "deadline": "u.sale_date, u.item_id",
    "rate": "u.min_price_krw::float / nullif(u.appraisal_krw, 0), u.sale_date",
    "appraisal": "u.appraisal_krw desc nulls last",
    "price": "u.min_price_krw nulls last",
    "failed": "u.failed_count desc nulls last, u.sale_date",
}

# 손님에게 보이는 물건 조건은 규칙 FIND-03 한 곳(11/8)
_BASE = f"""
from core.items i
join core.cases c using (case_id)
{ANALYSIS_JOIN}
where {COURT_VISIBLE}
"""


_ONBID_BASE = f"""
from core.onbid_items o
where {ONBID_VISIBLE}
"""
_COURT_SEL = """select i.item_id, 'court' as source, c.court_code, c.case_no, i.item_no, i.usage_name, i.address,
       i.building_area_m2, i.appraisal_krw, i.min_price_krw, i.failed_count, i.sale_date,
       a.result -> 'signals' as signals, a.result -> 'market' as market, null::text as kind"""
_ONBID_SEL = """select o.item_id, 'onbid' as source, null::text as court_code, o.mng_no as case_no, 1 as item_no,
       o.usage_name, coalesce(o.address, o.title) as address,
       coalesce(o.building_m2, o.land_m2) as building_area_m2, o.appraisal_krw, o.min_price_krw, o.failed_count,
       (o.bid_end at time zone 'Asia/Seoul')::date as sale_date, null::jsonb as signals, null::jsonb as market,
       o.kind"""


def union_sql(f: dict[str, Any], where: str) -> str:
    """경매·공매를 한 표로(「함께 보기」가 기본)."""
    parts = []
    if f.get("source") != "onbid":
        parts.append(f"{_COURT_SEL} {_BASE} {where}")
    ow = onbid_where(f)
    if ow is not None:
        parts.append(f"{_ONBID_SEL} {_ONBID_BASE} {ow}")
    return "(" + " union all ".join(parts) + ") u"


def _row(r: dict[str, Any], today: date) -> dict[str, Any]:
    app, mn = r["appraisal_krw"], r["min_price_krw"]
    sig = [
        s
        for s in (r["signals"] or [])
        if s.get("level") in ("fatal", "high", "mid") and s.get("status") != "모름"
    ]
    mkt = (r["market"] or {}).get("price_krw") if r["market"] else None
    return {
        "item_id": r["item_id"],
        "source": r["source"],
        "court": (
            f"공매·{KIND_KO.get(r['kind'], '')}".rstrip("·")
            if r["source"] == "onbid"
            else COURT_NAME.get(r["court_code"], r["court_code"])
        ),
        "case_no": r["case_no"],
        "item_no": r["item_no"],
        "usage": r["usage_name"],
        "address": r["address"],
        "area_m2": float(r["building_area_m2"]) if r["building_area_m2"] else None,
        "appraisal_krw": app,
        "min_price_krw": mn,
        "min_rate": round(mn * 100 / app) if app and mn else None,
        "failed_count": r["failed_count"],
        "sale_date": r["sale_date"].isoformat() if r["sale_date"] else None,
        "d_day": (r["sale_date"] - today).days if r["sale_date"] else None,
        "market_krw": mkt,
        "signal": sig[0]["title"] if sig else None,
        "fatal": bool(sig and sig[0].get("level") == "fatal"),
    }


def search(f: dict[str, Any], today: date, *, sort: str, page: int, limit: int) -> dict[str, Any]:
    where, p = build_where(f, today)
    p.update(limit=limit, offset=(page - 1) * limit)
    u = union_sql(f, where)
    order = SORTS.get(sort, SORTS["deadline"])
    with connect() as c:
        q_rows, q_sum, q_all = batch(
            c,
            [
                (f"select * from {u} order by {order} limit %(limit)s offset %(offset)s", p),
                (
                    f"""select count(*) as n, coalesce(sum(u.appraisal_krw), 0) as app_sum,
                       coalesce(avg(u.appraisal_krw), 0)::bigint as app_avg, coalesce(max(u.appraisal_krw), 0) as app_max,
                       coalesce(sum(u.min_price_krw), 0) as min_sum from {u}""",
                    p,
                ),
                (
                    f"select count(*) as n from {union_sql({'source': f.get('source')}, '')}",
                    {"today": today},
                ),
            ],
        )
        rows, s, all_n = q_rows.fetchall(), q_sum.fetchone(), q_all.fetchone()
    summary = dict(s or {})
    summary["all"] = all_n["n"] if all_n else 0
    return {
        "rows": [_row(r, today) for r in rows],
        "summary": summary,
        "page": page,
        "limit": limit,
    }


CSV_COLS = [
    ("court", "법원·공매"), ("case_no", "사건번호"), ("item_no", "물건번호"), ("usage", "용도"),
    ("address", "소재지"), ("area_m2", "면적㎡"), ("appraisal_krw", "감정가"), ("min_price_krw", "최저가"),
    ("min_rate", "최저가율%"), ("failed_count", "유찰"), ("sale_date", "매각기일"), ("market_krw", "시세"),
    ("signal", "주요 신호"),
]  # fmt: skip


def to_csv(rows: list[dict[str, Any]]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([h for _, h in CSV_COLS])
    for r in rows:
        w.writerow(["" if r.get(k) is None else r.get(k) for k, _ in CSV_COLS])
    return "﻿" + buf.getvalue()  # 엑셀에서 한글이 깨지지 않게


# 사건·문건 분석: 문건에 주의할 것이 있는 진행 사건 목록과 사건별 문건 흐름
# 목록에 올리는 분류(흔한 배당요구는 종기 뒤 신고일 때만), 속행 신청은 정지 뒤 맥락으로만 표시
WATCH_CATS = (
    "회생·파산", "정지·취하 시도", "매각조건 변경", "유치권 신고", "채권자 바뀜", "기일 연기·변경 신청",
)  # fmt: skip
SHOW_CATS = (*WATCH_CATS, "경매 속행 신청")


def cases(category: str | None, q: str | None, today: date) -> list[dict[str, Any]]:
    """진행 물건이 있는 사건 중 중요 문건(high·mid 중 WATCH_CATS 또는 종기 뒤 신고)이 있는 것."""
    p: dict[str, Any] = {"today": today, "cats": list(WATCH_CATS), "show": list(SHOW_CATS)}
    extra = ""
    if category == "종기 뒤 신고":
        extra += " and e.after_deadline"
    elif category:
        extra += " and e.category = %(cat)s"
        p["cat"] = category
    if q:
        extra += " and (c.case_no ilike %(q)s or i.address ilike %(q)s)"
        p["q"] = f"%{q.strip()}%"
    sql = f"""
    select c.case_id, c.court_code, c.case_no, min(i.sale_date) as sale_date,
           (array_agg(i.item_id order by i.sale_date, i.item_no))[1] as item_id,
           (array_agg(coalesce(i.gu, i.sigungu, '') || ' ' || coalesce(i.building_desc, i.usage_name, '')
                      order by i.sale_date, i.item_no))[1] as place,
           (select array_agg(distinct e2.category) from core.case_events e2 where e2.case_id = c.case_id
              and e2.category = any(%(show)s)) as flags,
           (select max(e3.event_date) from core.case_events e3 where e3.case_id = c.case_id
              and (e3.category = any(%(cats)s) or e3.after_deadline)) as last_date,
           (select count(*) from core.case_events e4 where e4.case_id = c.case_id and e4.after_deadline) as late
    from core.cases c
    join core.items i on i.case_id = c.case_id and i.sale_date >= %(today)s and i.status_code is distinct from 'gone'
    where exists (select 1 from core.case_events e where e.case_id = c.case_id
                  and (e.category = any(%(cats)s) and e.importance in ('high','mid') or e.after_deadline) {extra})
    group by c.case_id, c.court_code, c.case_no
    order by last_date desc nulls last limit 200"""
    with connect() as c:
        rows = c.execute(sql, p).fetchall()
    return [
        {
            **r,
            "court": COURT_NAME.get(r["court_code"], r["court_code"]),
            "sale_date": r["sale_date"].isoformat() if r["sale_date"] else None,
            "d_day": (r["sale_date"] - today).days if r["sale_date"] else None,
            "last_date": r["last_date"].isoformat() if r["last_date"] else None,
            "flags": sorted(
                r["flags"] or [], key=lambda x: WATCH_CATS.index(x) if x in WATCH_CATS else 99
            ),
        }
        for r in rows
    ]


def case_detail(case_id: str, today: date) -> dict[str, Any] | None:
    with connect() as c:
        head = c.execute(
            "select case_id, court_code, case_no, claim_deadline, dept_name from core.cases where case_id = %s",
            (case_id,),
        ).fetchone()
        if not head:
            return None
        items = c.execute(
            """select item_id, item_no, sale_date, usage_name, address, min_price_krw, appraisal_krw
               from core.items where case_id = %s and status_code is distinct from 'gone'
               order by item_no""",
            (case_id,),
        ).fetchall()
        ev = c.execute(
            """select event_date, kind, category, importance, after_deadline, text_masked
               from core.case_events where case_id = %s order by event_date, event_id""",
            (case_id,),
        ).fetchall()
    prog = judge_progress([(e["event_date"], e["category"]) for e in ev if e["event_date"]])
    counts: dict[str, int] = {}
    for e in ev:
        counts[e["category"]] = counts.get(e["category"], 0) + 1
    return {
        "case_id": head["case_id"],
        "court": COURT_NAME.get(head["court_code"], head["court_code"]),
        "case_no": head["case_no"],
        "dept": head["dept_name"],
        "claim_deadline": head["claim_deadline"].isoformat() if head["claim_deadline"] else None,
        "progress": prog.value,
        "items": [
            {
                **i,
                "sale_date": i["sale_date"].isoformat() if i["sale_date"] else None,
                "d_day": (i["sale_date"] - today).days if i["sale_date"] else None,
            }
            for i in items
        ],
        "counts": sorted(counts.items(), key=lambda x: -x[1]),
        "events": [
            {**e, "event_date": e["event_date"].isoformat() if e["event_date"] else None}
            for e in ev
        ],
    }


# 낙찰 사례와 시장 분석 + 낙찰가 성적표 (특수 사건·지분은 통계에서 뺌)
def _market_where(f: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    sql = (
        " where s.result = 'sold' and s.sale_rate is not null and s.sale_date >= %(since)s"
        " and not coalesce(s.is_special_case, false) and not coalesce(s.is_share, false)"
        f" and coalesce(s.usage_name, '') !~ '{VEHICLES}'"  # 부동산만
    )
    p: dict[str, Any] = {"since": f["since"]}
    if f.get("sido"):
        sql += " and s.sido = %(sido)s"
        p["sido"] = f["sido"]
    if f.get("sigungu"):
        sql += " and s.address like %(sgg)s"
        p["sgg"] = f"% {f['sigungu']} %"
    if f.get("court"):
        sql += " and s.court_code = %(court)s"
        p["court"] = f["court"]
    groups = [USAGE_GROUPS[g] for g in f.get("usage") or [] if g in USAGE_GROUPS]
    if groups:
        sql += " and s.usage_name ~ %(usage_re)s"
        p["usage_re"] = "|".join(f"({g})" for g in groups)
    return sql, p


_MED = "round(percentile_cont(0.5) within group (order by s.sale_rate)::numeric, 1)"


def market(f: dict[str, Any], today: date) -> dict[str, Any]:
    where, p = _market_where(f)
    case = " ".join(f"when s.usage_name ~ '{v}' then '{k}'" for k, v in USAGE_GROUPS.items())
    with connect() as c:
        qs = batch(
            c,
            [
                (
                    f"select s.court_code, count(*) as n, {_MED} as p50 from core.sale_results s {where}"
                    " group by 1 order by 2 desc",
                    p,
                ),
                (
                    f"select least(s.failed_count, 4) as failed, count(*) as n, {_MED} as p50"
                    f" from core.sale_results s {where} and s.failed_count is not null group by 1 order by 1",
                    p,
                ),
                (
                    f"select to_char(s.sale_date, 'YYYY-MM') as month, count(*) as n, {_MED} as p50"
                    f" from core.sale_results s {where} group by 1 order by 1",
                    p,
                ),
                (
                    f"select case {case} else 'etc' end as usage, count(*) as n, {_MED} as p50"
                    f" from core.sale_results s {where} group by 1 order by 2 desc",
                    p,
                ),
                (
                    f"""select s.sale_date, s.court_code, s.case_no, s.usage_name, s.address, s.building_area_m2,
                       s.appraisal_krw, s.winning_bid_krw, s.sale_rate, s.failed_count, s.item_id
                from core.sale_results s {where} order by s.sale_date desc, s.result_id desc limit 100""",
                    p,
                ),
                (
                    """with pred as (
                 select s.item_id, s.sale_rate, (a.result -> 'sale_rate' ->> 'p25')::numeric as p25,
                        (a.result -> 'sale_rate' ->> 'p75')::numeric as p75
                 from core.sale_results s
                 join lateral (select result from analysis.item_analysis x where x.item_id = s.item_id
                               and x.computed_at::date < s.sale_date order by x.version desc limit 1) a on true
                 where s.result = 'sold' and s.sale_rate is not null and a.result -> 'sale_rate' ->> 'p25' is not null and a.result -> 'sale_rate' ->> 'p75' is not null
                   and not coalesce((a.result ->> 'new_item')::boolean, false))
               select count(*) as n,
                      count(*) filter (where sale_rate between p25 and p75) as inside,
                      count(*) filter (where sale_rate < p25) as below,
                      count(*) filter (where sale_rate > p75) as above
               from pred""",
                    None,
                ),
                (
                    """select s.sale_date, s.court_code, s.case_no, s.address, s.sale_rate, s.item_id,
                      (a.result -> 'sale_rate' ->> 'p25')::numeric as p25,
                      (a.result -> 'sale_rate' ->> 'p75')::numeric as p75
               from core.sale_results s
               join lateral (select result from analysis.item_analysis x where x.item_id = s.item_id
                             and x.computed_at::date < s.sale_date order by x.version desc limit 1) a on true
               where s.result = 'sold' and s.sale_rate is not null and a.result -> 'sale_rate' ->> 'p25' is not null and a.result -> 'sale_rate' ->> 'p75' is not null
                 and not coalesce((a.result ->> 'new_item')::boolean, false)
               order by greatest((a.result -> 'sale_rate' ->> 'p25')::numeric - s.sale_rate,
                                 s.sale_rate - (a.result -> 'sale_rate' ->> 'p75')::numeric) desc
               limit 5""",
                    None,
                ),
            ],
        )
        by_court, by_failed, by_month, by_usage, rows = (q.fetchall() for q in qs[:5])
        score = qs[5].fetchone()
        misses = qs[6].fetchall()
    return {
        "by_usage": by_usage,
        "misses": [
            {
                **r,
                "court": COURT_NAME.get(r["court_code"], r["court_code"]),
                "sale_date": r["sale_date"].isoformat(),
                "sale_rate": float(r["sale_rate"]),
                "p25": float(r["p25"]),
                "p75": float(r["p75"]),
            }
            for r in misses
        ],
        "by_court": [
            {**r, "court": COURT_NAME.get(r["court_code"], r["court_code"])} for r in by_court
        ],
        "by_failed": by_failed,
        "by_month": by_month,
        "cases": [
            {
                **r,
                "court": COURT_NAME.get(r["court_code"], r["court_code"]),
                "sale_date": r["sale_date"].isoformat(),
                "building_area_m2": float(r["building_area_m2"]) if r["building_area_m2"] else None,
                "sale_rate": float(r["sale_rate"]),
            }
            for r in rows
        ],
        "scorecard": dict(score or {}),
    }


# ── 공매 시장(전국, core.onbid_results) ─────────────────────────
# 공매 낙찰가율은 최저가 대비(100%를 넘는 게 보통) — 경매 숫자와 섞지 않고 탭을 나눔.
_O_MED = "round(percentile_cont(0.5) within group (order by s.rate_min)::numeric, 1)"
_O_MED_APP = "round(percentile_cont(0.5) within group (order by s.rate_appraisal)::numeric, 1)"
_O_USAGE = "coalesce(s.usage_s, s.usage_m, '')"
_O_BIDDERS = (
    "case when s.bidders <= 1 then '혼자' when s.bidders = 2 then '2명' "
    "when s.bidders <= 4 then '3~4명' else '5명+' end"
)


def onbid_market_where(f: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    sql = (
        " where s.result = '낙찰' and s.rate_min is not null and s.opened_at >= %(since)s"
        " and coalesce(s.disposal, '매각') = '매각'"
    )
    p: dict[str, Any] = {"since": f["since"]}
    if f.get("sido"):
        sql += " and s.sido = %(sido)s"
        p["sido"] = f["sido"]
    if f.get("sigungu"):
        sql += " and s.title like %(sgg)s"
        p["sgg"] = f"% {f['sigungu']} %"
    groups = [USAGE_GROUPS[g] for g in f.get("usage") or [] if g in USAGE_GROUPS]
    if groups:
        sql += f" and {_O_USAGE} ~ %(usage_re)s"
        p["usage_re"] = "|".join(f"({g})" for g in groups)
    return sql, p


def onbid_market(f: dict[str, Any]) -> dict[str, Any]:
    where, p = onbid_market_where(f)
    case = " ".join(f"when {_O_USAGE} ~ '{v}' then '{k}'" for k, v in USAGE_GROUPS.items())
    stat = f"count(*) as n, {_O_MED} as p50, {_O_MED_APP} as p50_app"
    frm = f"from core.onbid_results s {where}"
    with connect() as c:
        qs = batch(
            c,
            [
                (f"select s.sido, {stat} {frm} group by 1 order by 2 desc", p),
                (f"select {_O_BIDDERS} as bidders, {stat} {frm} and s.bidders is not null"
                 " group by 1 order by min(s.bidders)", p),
                (f"select least(coalesce(s.failed_round, 0), 4)::int as failed, {stat} {frm} group by 1 order by 1", p),
                (f"select to_char(s.opened_at at time zone 'Asia/Seoul', 'YYYY-MM') as month, {stat} {frm}"
                 " group by 1 order by 1", p),
                (f"select case {case} else 'etc' end as usage, {stat} {frm} group by 1 order by 2 desc", p),
                (f"""select (s.opened_at at time zone 'Asia/Seoul')::date::text as sale_date, s.mng_no, s.kind_name,
                           {_O_USAGE} as usage_name, s.title, s.building_m2, s.appraisal_krw, s.min_price_krw,
                           s.win_krw, s.rate_min, s.rate_appraisal, s.bidders
                    {frm} order by s.opened_at desc limit 100""", p),
            ],
        )  # fmt: skip
        by_sido, by_bidders, by_failed, by_month, by_usage, rows = (q.fetchall() for q in qs)

    def num(rs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                k: (float(v) if k.startswith(("p50", "rate_")) and v is not None else v)
                for k, v in r.items()
            }
            for r in rs
        ]

    return {
        "basis": "최저가 대비",
        "by_sido": num(by_sido),
        "by_bidders": num(by_bidders),
        "by_failed": num(by_failed),
        "by_month": num(by_month),
        "by_usage": num(by_usage),
        "cases": num(rows),
    }
