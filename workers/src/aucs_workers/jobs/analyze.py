"""물건 분석: DB에서 자료를 모아 규칙(packages/rules)을 돌리고 analysis 표에 씁니다.

    uv run python -m aucs_workers.jobs.analyze            # 매각기일이 다가오는 물건 전부
    uv run python -m aucs_workers.jobs.analyze --item B000250-2025타경55580-1

입력이 같으면(input_hash) 다시 쓰지 않고, 바뀌면 버전을 올립니다.
"""

import argparse
import hashlib
import json
from datetime import date, timedelta
from typing import Any

import psycopg
from aucs_rules import ENGINE_VERSION
from aucs_rules.costs import commercial_over_limit
from aucs_rules.price import Trade, market_price
from aucs_rules.progress import judge_progress
from aucs_rules.risk import signals, top_signal
from aucs_rules.sale_rate import Sale, court_cell, local_peers, new_item, rate_range
from aucs_rules.small_lease_region import region_class
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from aucs_workers.db import connect
from aucs_workers.jobs.runlog import run

COMMERCIAL_WORDS = ("상가", "근린", "점포", "사무실", "공장")


def trade_type(usage: str | None, building_desc: str | None) -> str | None:
    """물건 용도 → 실거래 종류. 상가·근린이 섞인 용도는 시세를 내지 않습니다."""
    u = usage or ""
    if u == "아파트":
        return "apt"
    if u == "오피스텔" or (u == "상가,오피스텔,근린시설" and "오피스텔" in (building_desc or "")):
        return "officetel"
    if u in ("다세대", "연립주택,다세대,빌라"):
        return "rowhouse"
    return None


def load_market(
    conn: psycopg.Connection, item: dict[str, Any], today: date
) -> dict[str, Any] | None:
    """같은 법정동·같은 지번(같은 단지·건물)의 최근 24개월 매매로 시세. 전용 ±3㎡."""
    kind = trade_type(item.get("usage_name"), item.get("building_desc"))
    area = item.get("building_area_m2")
    if not kind or not area or not item.get("region_code") or not item.get("lot_no"):
        return None
    rows = conn.execute(
        """select deal_date, price_krw, area_m2, floor, build_year from core.trades
           where region_code = %s and prop_type = %s and deal_kind = 'sale' and lot_no = %s
             and deal_date >= %s and price_krw > 0""",
        (item["region_code"], kind, item["lot_no"], today - timedelta(days=730)),
    ).fetchall()
    lot = item["lot_no"]
    trades = [Trade(r[0], int(r[1]), float(r[2]), r[3], lot, r[4]) for r in rows]
    res = market_price(trades, as_of=today, complex_name=lot, area_m2=float(area))
    if res.value is None:
        return None
    recent = sorted(res.evidence, key=lambda e: e["date"], reverse=True)[:5]
    return {**res.value, "recent": recent}


def commercial_over(
    item: dict[str, Any], tenants: list[dict[str, Any]], table: dict[str, Any] | None, today: date
) -> bool:
    """상가 물건에서 환산보증금이 지역 한도를 넘는 임차인이 있는지 (T3)."""
    usage = item.get("usage_name") or ""
    if not table or not any(w in usage for w in COMMERCIAL_WORDS):
        return False
    cls = region_class(item.get("sido"), item.get("sigungu"), None, today).value
    for t in tenants:
        r = commercial_over_limit(
            t.get("deposit_krw"), t.get("monthly_rent_krw"), sido=item.get("sido"),
            sigungu=item.get("sigungu"), region_class=cls, table=table,
        ).value  # fmt: skip
        if r and r["over"]:
            return True
    return False


def build_facts(
    item: dict[str, Any],
    events: list[dict[str, Any]],
    tenants: list[dict[str, Any]],
    has_status_report: bool,
    commercial_over_limit: bool = False,
) -> dict[str, Any]:
    """물건·문건·임차인 → 위험 신호 규칙이 읽는 사실 묶음 (순수 함수)."""
    cats = {e["category"] for e in events}
    progress = judge_progress([(e["event_date"], e["category"]) for e in events if e["event_date"]])
    return {
        "is_share": item.get("is_share"),
        "usage_code": item.get("usage_code"),
        "usage_text": f"{item.get('usage_name') or ''} {item.get('building_desc') or ''}",
        "note": item.get("note_masked"),
        "lien_reported": "유치권 신고" in cats,
        "rehab_or_bankrupt": "회생·파산" in cats,
        "stop_attempts": progress.value == "기일이 바뀔 수 있음",
        "creditor_changed": "채권자 바뀜" in cats,
        "claim_after_deadline": any(e["after_deadline"] for e in events),
        "commercial_over_limit": commercial_over_limit,
        **({"tenants_checked": False} if not has_status_report else {}),
    }


def _hash(obj: Any) -> str:
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, default=str, ensure_ascii=False).encode()
    ).hexdigest()[:16]


def analyze_item(
    conn: psycopg.Connection,
    item_id: str,
    sales: list[Sale],
    today: date,
    commercial_table: dict[str, Any] | None = None,
) -> bool:
    cur = conn.cursor(row_factory=dict_row)
    item = cur.execute("select * from core.items where item_id = %s", (item_id,)).fetchone()
    if not item:
        return False
    events = cur.execute(
        "select event_date, category, after_deadline from core.case_events where case_id = %s",
        (item["case_id"],),
    ).fetchall()
    tenants = cur.execute(
        "select move_in_date, deposit_krw, monthly_rent_krw from core.tenants where case_id = %s",
        (item["case_id"],),
    ).fetchall()
    has_sr = bool(
        cur.execute(
            "select 1 from raw.court_doc_raw where case_id = %s and doc_kind = 'status_report' limit 1",
            (item["case_id"],),
        ).fetchone()
    )
    over = commercial_over(item, tenants, commercial_table, today)
    market = load_market(conn, item, today)
    facts = build_facts(item, events, tenants, has_sr, over)
    if market:
        facts.update(
            market_price_krw=market["price_krw"], appraisal_krw=item["appraisal_krw"], as_of=today
        )
    sig = signals(facts)
    rates = rate_range(
        sales, as_of=today, sido=item["sido"], sigungu=item["sigungu"], usage_name=item["usage_name"],
        area_m2=float(item["building_area_m2"]) if item["building_area_m2"] else None, failed_count=item["failed_count"],
    )  # fmt: skip
    app, mn = item["appraisal_krw"], item["min_price_krw"]
    min_rate = round(mn * 100 / app, 1) if app and mn else None
    base_p50 = rates.value["p50"] if rates.value else None
    court = court_cell(
        sales, as_of=today, court_code=item["case_id"].split("-")[0], usage_name=item["usage_name"],
        min_rate=min_rate, base_p50=base_p50,
    )  # fmt: skip
    review_p50 = court.value["p50"] if court.value and court.value["use_as_base"] else base_p50
    peers = local_peers(
        sales, as_of=today, sigungu=item["sigungu"], usage_name=item["usage_name"],
        min_rate=min_rate, review_p50=review_p50,
    )  # fmt: skip
    top = top_signal(sig)
    result = {
        "signals": [
            {
                "rule_id": s.rule_id,
                "level": s.level,
                "title": s.title,
                "status": s.status,
                "ftype": s.ftype,
            }
            for s in sig
        ],
        "top": {"level": top.level, "title": top.title} if top else None,
        "sale_rate": rates.value,
        "court_cell": court.value,
        "local_peers": peers.value,
        "new_item": new_item(
            item["failed_count"], app, market["price_krw"] if market else None
        ).value,
        "market": market,
        "tenant_count": len(tenants),
    }
    h = _hash({"facts": facts, "rates": rates.value, "court": court.value, "peers": peers.value,
               "tenants": tenants, "market": market, "engine": ENGINE_VERSION})  # fmt: skip
    last = cur.execute(
        "select version, input_hash from analysis.item_analysis where item_id = %s order by version desc limit 1",
        (item_id,),
    ).fetchone()
    if last and last["input_hash"] == h:
        return False
    version = (last["version"] + 1) if last else 1
    cur.execute(
        "insert into analysis.item_analysis (item_id, version, engine_version, input_hash, result) values (%s,%s,%s,%s,%s)",
        (item_id, version, ENGINE_VERSION, h, Jsonb(result)),
    )
    cur.execute("delete from analysis.risk_signals where item_id = %s", (item_id,))
    cur.executemany(
        "insert into analysis.risk_signals (item_id, rule_id, level, status, title, evidence, engine_version) values (%s,%s,%s,%s,%s,%s,%s)",
        [
            (item_id, s.rule_id, s.level, str(s.status), s.title, Jsonb(s.evidence), ENGINE_VERSION)
            for s in sig
        ],
    )
    for kind, ok in [("item", True), ("status_report", has_sr), ("deliveries", bool(events))]:
        cur.execute(
            "insert into analysis.item_data_status (item_id, data_kind, status, computed_at) values (%s,%s,%s, now())"
            " on conflict (item_id, data_kind) do update set status = excluded.status, computed_at = now()",
            (item_id, kind, "extracted" if ok else "missing"),
        )
    return True


def load_sales(conn: psycopg.Connection, today: date) -> list[Sale]:
    """최근 12개월 매각 사례 (면적은 우리 물건 표에서 이어 붙임)."""
    rows = conn.execute(
        """select s.sale_date, s.sido, i.sigungu, s.usage_name, coalesce(s.building_area_m2, i.building_area_m2),
                  s.failed_count, s.sale_rate, s.is_share or s.is_special_case, s.address, s.court_code,
                  case when s.appraisal_krw > 0 then s.min_price_krw * 100.0 / s.appraisal_krw end
           from core.sale_results s left join core.items i on i.item_id = s.item_id
           where s.result = 'sold' and s.sale_rate is not null and s.sale_date >= %s""",
        (today - timedelta(days=365),),
    ).fetchall()
    out = []
    for d, sido, sigungu, usage, area, failed, rate, special, address, court, min_rate in rows:
        area_f = float(area) if area else None
        sg = sigungu or sigungu_from_address(address)
        mr = float(min_rate) if min_rate is not None else None
        out.append(Sale(d, sido, sg, usage, area_f, failed, float(rate), bool(special), court, mr))
    return out


def sigungu_from_address(address: str | None) -> str | None:
    """「경기 용인시 수지구 …」 → 용인시, 「서울 강남구 …」 → 강남구."""
    parts = (address or "").split()
    if len(parts) > 1 and parts[1][-1:] in ("시", "군", "구"):
        return parts[1]
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--item")
    a = ap.parse_args()
    today = date.today()
    with connect() as conn, run(conn, "analyze", "물건 분석") as job:
        sales = load_sales(conn, today)
        row = conn.execute(
            "select value from ref.rule_tables where rule_key = 'commercial_lease_limit' and valid_from <= %s"
            " order by valid_from desc limit 1",
            (today,),
        ).fetchone()
        commercial_table = row[0] if row else None
        ids = [a.item] if a.item else [r[0] for r in conn.execute(
            "select item_id from core.items where sale_date >= %s", (today - timedelta(days=7),)).fetchall()]  # fmt: skip
        for item_id in ids:
            if analyze_item(conn, item_id, sales, today, commercial_table):
                job.count += 1
            conn.commit()
    print(f"분석 {job.count:,}건 (대상 {len(ids):,})")


if __name__ == "__main__":
    main()
