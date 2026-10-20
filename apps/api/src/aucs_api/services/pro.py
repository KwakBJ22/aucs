"""PC 전문가 「전체 물건」 표: 조건 여러 개로 거르고, 고른 물건 요약·CSV.
(지금의 경매레이더 화면을 옮긴 것. 전문가 이용권 잠금은 이용권을 붙일 때.)"""

import csv
import io
from datetime import date
from typing import Any

from aucs_rules.progress import judge_progress

from aucs_api.db import batch, connect
from aucs_api.services.items import COURT_NAME

USAGE_GROUPS = {
    "apt": "아파트",
    "villa": "다세대|연립|빌라",
    "officetel": "오피스텔",
    "house": "단독|다가구",
    "shop": "상가|근린|점포|사무|공장|창고|숙박|업무",
    "land": "대지|전답|임야|토지|잡종|^전$|^답$",
}
EXCLUDE_RULES = {
    "share": ["risk.share"],
    "special": ["risk.special_condition"],
    "villa": ["risk.neighborhood_villa"],
    "stop": ["risk.stop", "risk.withdraw"],
    "lien": ["risk.lien"],
    "senior": ["risk.senior_tenant", "risk.prior_rights", "risk.lease_reg"],
    "superficies": ["risk.superficies", "risk.land_right"],
    "illegal": ["risk.illegal"],
    "farmland": ["risk.farmland"],
    "resale": ["risk.resale"],
}
# 초보자 안전 모드: 한 번에 빼는 7가지(05 화면 설계)
SAFE_MODE = ["share", "lien", "senior", "superficies", "villa", "special", "stop"]
SORTS = {
    "deadline": "i.sale_date, i.item_id",
    "rate": "i.min_price_krw::float / nullif(i.appraisal_krw, 0), i.sale_date",
    "appraisal": "i.appraisal_krw desc nulls last",
    "price": "i.min_price_krw nulls last",
    "failed": "i.failed_count desc nulls last, i.sale_date",
}

_BASE = """
from core.items i
join core.cases c using (case_id)
left join lateral (select result from analysis.item_analysis x where x.item_id = i.item_id order by version desc limit 1) a on true
where i.display_policy = 'public' and i.sale_date >= %(today)s
  and i.status_code is distinct from 'gone' and a.result is not null
"""


def build_where(f: dict[str, Any], today: date) -> tuple[str, dict[str, Any]]:
    """조건 → SQL 조각과 값 (순수 함수, 값은 모두 바인딩)."""
    sql = ""
    p: dict[str, Any] = {"today": today}
    if f.get("sido"):
        sql += " and i.sido = %(sido)s"
        p["sido"] = f["sido"]
    if f.get("sigungu"):
        sql += " and i.sigungu = any(%(sigungu)s)"
        p["sigungu"] = list(f["sigungu"])
    if f.get("court"):
        sql += " and c.court_code = any(%(court)s)"
        p["court"] = list(f["court"])
    groups = [USAGE_GROUPS[g] for g in f.get("usage") or [] if g in USAGE_GROUPS]
    if groups:
        sql += " and i.usage_name ~ %(usage_re)s"
        p["usage_re"] = "|".join(f"({g})" for g in groups)
    for key, col, op in (
        ("failed_min", "i.failed_count", ">="),
        ("failed_max", "i.failed_count", "<="),
        ("app_min", "i.appraisal_krw", ">="),
        ("app_max", "i.appraisal_krw", "<="),
        ("price_max", "i.min_price_krw", "<="),
        ("area_min", "i.building_area_m2", ">="),
        ("area_max", "i.building_area_m2", "<="),
    ):
        if f.get(key) is not None:
            sql += f" and coalesce({col}, 0) {op} %({key})s"
            p[key] = f[key]
    if f.get("rate_max") is not None:
        sql += " and i.min_price_krw * 100 <= %(rate_max)s * i.appraisal_krw"
        p["rate_max"] = f["rate_max"]
    if f.get("days_max") is not None:
        sql += " and i.sale_date <= %(today)s + %(days_max)s"
        p["days_max"] = f["days_max"]
    rules = [r for k in f.get("exclude") or [] for r in EXCLUDE_RULES.get(k, [])]
    if rules:
        sql += """ and not exists (select 1 from jsonb_array_elements(coalesce(a.result -> 'signals', '[]'::jsonb)) s
                   where s ->> 'rule_id' = any(%(ex_rules)s) and s ->> 'status' <> '모름')"""
        p["ex_rules"] = rules
    if "fatal" in (f.get("exclude") or []):
        sql += """ and not exists (select 1 from jsonb_array_elements(coalesce(a.result -> 'signals', '[]'::jsonb)) s
                   where s ->> 'level' = 'fatal')"""
    if f.get("q"):
        sql += (
            " and (i.address ilike %(q)s or i.building_desc ilike %(q)s or c.case_no ilike %(q)s)"
        )
        p["q"] = f"%{f['q'].strip()}%"
    return sql, p


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
        "court": COURT_NAME.get(r["court_code"], r["court_code"]),
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
    sel = """select i.item_id, c.court_code, c.case_no, i.item_no, i.usage_name, i.address, i.building_area_m2,
                    i.appraisal_krw, i.min_price_krw, i.failed_count, i.sale_date,
                    a.result -> 'signals' as signals, a.result -> 'market' as market"""
    order = SORTS.get(sort, SORTS["deadline"])
    with connect() as c:
        q_rows, q_sum, q_all = batch(
            c,
            [
                (f"{sel} {_BASE} {where} order by {order} limit %(limit)s offset %(offset)s", p),
                (
                    f"""select count(*) as n, coalesce(sum(i.appraisal_krw), 0) as app_sum,
                       coalesce(avg(i.appraisal_krw), 0)::bigint as app_avg, coalesce(max(i.appraisal_krw), 0) as app_max,
                       coalesce(sum(i.min_price_krw), 0) as min_sum {_BASE} {where}""",
                    p,
                ),
                (f"select count(*) as n {_BASE}", {"today": today}),
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
    ("court", "법원"), ("case_no", "사건번호"), ("item_no", "물건번호"), ("usage", "용도"),
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
        " and coalesce(s.usage_name, '') !~ '자동차|중기|선박|항공기'"  # 부동산만
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
                 where s.result = 'sold' and s.sale_rate is not null and a.result -> 'sale_rate' is not null
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
               where s.result = 'sold' and s.sale_rate is not null and a.result -> 'sale_rate' is not null
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
