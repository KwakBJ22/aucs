"""PC 전문가 「전체 물건」 표: 조건 여러 개로 거르고, 고른 물건 요약·CSV.
(지금의 경매레이더 화면을 옮긴 것. 전문가 이용권 잠금은 이용권을 붙일 때.)"""

import csv
import io
from datetime import date
from typing import Any

from aucs_api.db import connect
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
    "stop": ["risk.stop"],
}
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
    sql, p = "", {"today": today}
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
        rows = c.execute(
            f"{sel} {_BASE} {where} order by {order} limit %(limit)s offset %(offset)s", p
        ).fetchall()
        s = c.execute(
            f"""select count(*) as n, coalesce(sum(i.appraisal_krw), 0) as app_sum,
                       coalesce(avg(i.appraisal_krw), 0)::bigint as app_avg, coalesce(max(i.appraisal_krw), 0) as app_max,
                       coalesce(sum(i.min_price_krw), 0) as min_sum {_BASE} {where}""",
            p,
        ).fetchone()
        all_n = c.execute(f"select count(*) as n {_BASE}", {"today": today}).fetchone()
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
