"""물건 분석: DB에서 자료를 모아 규칙(packages/rules)을 돌리고 analysis 표에 씁니다.

    uv run python -m aucs_workers.jobs.analyze            # 매각기일이 다가오는 물건 전부
    uv run python -m aucs_workers.jobs.analyze --item B000250-2025타경55580-1
    uv run python -m aucs_workers.jobs.analyze --stale     # 새 물건·바뀐 물건·새 서류 받은 물건만 (아침 묶음)

입력이 같으면(input_hash) 다시 쓰지 않고, 바뀌면 버전을 올립니다.
"""

import argparse
import hashlib
import json
import re
from datetime import date, timedelta
from typing import Any

import psycopg
from aucs_rules import ENGINE_VERSION
from aucs_rules.appraisal_parts import appraisal_parts
from aucs_rules.appraisal_points import appraisal_facts, parse_points, plan_zone_of_parcel
from aucs_rules.building import lot_key, parse_jibun, summarize
from aucs_rules.calc import CASH_TABLE_KEYS, area_class, cash_at_min
from aucs_rules.costs import commercial_over_limit
from aucs_rules.land_value import HouseTrade, land_value
from aucs_rules.price import Trade, market_price, trade_region
from aucs_rules.progress import judge_progress
from aucs_rules.risk import signals, top_signal
from aucs_rules.sale_rate import (
    Sale,
    court_cell,
    effective_failed,
    local_peers,
    new_item,
    rate_range,
)
from aucs_rules.small_lease_region import region_class
from aucs_rules.spec_facts import spec_facts
from aucs_rules.tenants import Tenant, base_date_of, tax_before_tenant
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from aucs_workers.collectors.official_prices import pnu_of
from aucs_workers.db import connect
from aucs_workers.jobs.redev_match import find_zone, near_zone
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
        (trade_region(item["region_code"]), kind, item["lot_no"], today - timedelta(days=730)),
    ).fetchall()
    lot = item["lot_no"]
    trades = [Trade(r[0], int(r[1]), float(r[2]), r[3], lot, r[4]) for r in rows]
    res = market_price(trades, as_of=today, complex_name=lot, area_m2=float(area))
    if res.value is None:
        return None
    recent = sorted(res.evidence, key=lambda e: e["date"], reverse=True)[:5]
    return {**res.value, "recent": recent}


def commercial_over(
    item: dict[str, Any],
    tenants: list[dict[str, Any]],
    table: dict[str, Any] | None,
    today: date,
    overcrowded_hint: bool | None = None,
) -> bool:
    """상가 물건에서 환산보증금이 지역 한도를 넘는 임차인이 있는지 (T3)."""
    usage = item.get("usage_name") or ""
    if not table or not any(w in usage for w in COMMERCIAL_WORDS):
        return False
    cls = region_class(item.get("sido"), item.get("sigungu"), None, today, overcrowded_hint).value
    for t in tenants:
        r = commercial_over_limit(
            t.get("deposit_krw"), t.get("monthly_rent_krw"), sido=item.get("sido"),
            sigungu=item.get("sigungu"), region_class=cls, table=table,
        ).value  # fmt: skip
        if r and r["over"]:
            return True
    return False


def load_detail(cur: Any, item: dict[str, Any]) -> dict[str, Any]:
    """물건상세(item_detail_N) 원문의 dma_result — 명세서 칸 · 감정평가 요항을 함께 읽으려고 한 번만 부름."""
    row = cur.execute(
        "select payload from raw.court_doc_raw where case_id = %s and doc_kind = %s order by fetched_at desc limit 1",
        (item["case_id"], f"item_detail_{item.get('item_no') or 1}"),
    ).fetchone()
    return dict(((row or {}).get("payload") or {}).get("dma_result") or {})


def load_appraisal(cur: Any, item: dict[str, Any]) -> dict[str, Any]:
    """감정평가서 정보(raw 'appraisal' — 가격시점·작성일)와 원본에서 읽은 회사 이름(raw 'appraisal_pdf'), 11/4."""
    rows = cur.execute(
        """select distinct on (doc_kind) doc_kind, payload from raw.court_doc_raw
           where case_id = %s and doc_kind in ('appraisal', 'appraisal_pdf') order by doc_kind, fetched_at desc""",
        (item["case_id"],),
    ).fetchall()
    by = {r["doc_kind"]: r["payload"] or {} for r in rows}
    info = (by.get("appraisal") or {}).get("info") or {}
    ymd = str(info.get("dspslPrcCrtrYmd") or "")
    return {
        "price_date": date(int(ymd[:4]), int(ymd[4:6]), int(ymd[6:8])) if len(ymd) == 8 else None,
        "firm": (by.get("appraisal_pdf") or {}).get("firm"),
        "points": (by.get("appraisal_pdf") or {}).get("points") or [],  # 원본 요항표(11/11)
    }


def load_spec(detail: dict[str, Any]) -> dict[str, Any] | None:
    """물건상세의 명세서 칸 (작성 전이면 None)."""
    info = detail.get("dspslGdsDxdyInfo") or {}
    if not info.get("gdsSpcfcWrtYmd"):
        return None

    def clean(k: str) -> str | None:
        v = re.sub(r"<br\s*/?>", " ", str(info.get(k) or "")).strip()
        return v or None

    return {"keep": clean("ndstrcRghCtt"), "superficies": clean("sprfcExstcDts"),
            "remark": clean("gdsSpcfcRmk"), "item_remark": clean("dspslGdsRmk"),
            "base": clean("tprtyRnkHypthcStngDts")}  # fmt: skip


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


HOUSE_USES = ("단독주택다가구", "단독주택", "다가구주택")
HOUSE_MAIN = re.compile(r"단독|다가구|다중주택")


def load_land_value(
    cur: Any, item: dict[str, Any], bldg: dict[str, Any] | None, today: date,
    table: dict[str, Any] | None,
) -> dict[str, Any] | None:  # fmt: skip
    """단독·다가구: 같은 동 실거래로 땅값을 역산해 추정 시세 하단·가운데·상단(LAND-01). 지분 물건은 뺌."""
    if not table or not bldg or item.get("is_share") or not item.get("region_code"):
        return None
    if item.get("usage_name") not in HOUSE_USES and not HOUSE_MAIN.search(bldg.get("main_use") or ""):
        return None
    region = trade_region(item["region_code"])
    rows = cur.execute(
        """select deal_date, price_krw, area_m2, land_area_m2, build_year from core.trades
           where region_code = %s and prop_type = 'house' and deal_kind = 'sale'
             and deal_date >= %s and price_krw > 0 and land_area_m2 > 0 and area_m2 > 0""",
        (region, today - timedelta(days=round(int(table.get("months") or 24) * 30.4))),
    ).fetchall()
    trades = [HouseTrade(r["deal_date"], int(r["price_krw"]), float(r["area_m2"]),
                         float(r["land_area_m2"]), r["build_year"]) for r in rows]  # fmt: skip
    # 맞춰 보기: 같은 동 다른 단독·다가구의 법원 토지 감정가 ÷ 대지(감정가 나눔 · 건축물대장이 있는 것만)
    court = cur.execute(
        """select (a.result->'parts'->>'land_krw')::numeric / nullif((a.result->'building'->>'land_m2')::numeric, 0) as u
           from core.items i
           join lateral (select result from analysis.item_analysis x where x.item_id = i.item_id
                         order by version desc limit 1) a on true
           where i.region_code like %s and i.item_id <> %s and not i.is_share
             and a.result->'parts'->>'kind' = 'land_and_building'
             and (a.result->'building'->>'land_m2') is not null""",
        (region[:8] + "%", item["item_id"]),
    ).fetchall()
    approved = bldg.get("approved")
    res = land_value(
        land_m2=bldg.get("land_m2"), floor_area_m2=bldg.get("total_area_m2"),
        build_year=int(approved[:4]) if approved else None, trades=trades,
        court_units=[float(r["u"]) for r in court if r["u"]], as_of=today, table=table,
    )  # fmt: skip
    return res.value


def load_building(cur: Any, item: dict[str, Any], today: date) -> dict[str, Any] | None:
    """건축물대장(collectors/buildings) → 요약. 지번을 못 읽거나 아직 안 받았으면 None."""
    p = parse_jibun(item.get("lot_no"))
    if not p or not item.get("region_code"):
        return None
    lk = lot_key(*p)
    rows = cur.execute(
        "select kind, data from core.building_register where region_code = %s and lot_no = %s order by kind, seq",
        (item["region_code"], lk),
    ).fetchall()
    titles = [r["data"] for r in rows if r["kind"] == "title"]
    floors = [r["data"] for r in rows if r["kind"] == "floor"]
    usage = f"{item.get('usage_name') or ''} {item.get('building_desc') or ''}"
    return summarize(titles, floors, item.get("address"), usage, today)


def load_parcel_zone(cur: Any, item: dict[str, Any]) -> str | None:
    """필지 토지이용계획(collectors/land_use) → 'zone' / 'district' / 'planned'. 아직 안 받았으면 None."""
    pnu = pnu_of(item.get("region_code") or "", item.get("lot_no") or "")
    if not pnu:
        return None
    row = cur.execute("select uses from core.parcel_land_use where pnu = %s", (pnu,)).fetchone()
    return plan_zone_of_parcel(row["uses"]) if row else None


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
    cash_tables: dict[str, Any] | None = None,
    land_table: dict[str, Any] | None = None,
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
        "select move_in_date, fixed_date, deposit_krw, monthly_rent_krw, has_lease_registration from core.tenants where case_id = %s",
        (item["case_id"],),
    ).fetchall()
    has_sr = bool(
        cur.execute(
            "select 1 from raw.court_doc_raw where case_id = %s and doc_kind = 'status_report' limit 1",
            (item["case_id"],),
        ).fetchone()
    )
    detail = load_detail(cur, item)
    # 감정평가 요항(11/4 사용 허락): 화면 요점 + 맹지·좁은 길·개발제한·교육환경·토지거래허가·과밀억제 사실
    # 법원 요항을 아직 못 받았으면 받아 둔 감정평가서 원본의 요항표로(11/11)
    apr = load_appraisal(cur, item)
    points = parse_points(detail.get("aeeWevlMnpntLst") or apr["points"])
    af = appraisal_facts(points).value
    hint = bool(af.get("overcrowded")) if points else None
    # 감정가 나눔(11/7): 토지·건물 금액 · 제시외 건물 · 대지권 — 원본 없이 물건상세로
    parts = appraisal_parts(
        detail.get("gdsDspslObjctLst"),
        detail.get("gdsNotSugtBldLsstAll"),
        detail.get("rgltLandLstAll"),
    ).value
    over = commercial_over(item, tenants, commercial_table, today, hint)
    market = load_market(conn, item, today)
    facts = build_facts(item, events, tenants, has_sr, over)
    for k, v in af.items():
        facts.setdefault(k, v)
    if apr["price_date"]:  # 가격시점 — 감정가 저평가 · 오래된 감정 신호가 읽음
        facts.update(appraisal_date=apr["price_date"], as_of=today)
    # 매각물건명세서(물건상세에 들어 있음) → 위반건축·대지권·유치권·법정지상권·인수 권리, 비고는 특별조건 찾기에도
    spec = load_spec(detail)
    sf = spec_facts(spec)
    # 세금이 대항력 임차인보다 먼저일 수 있음(11/11): 말소기준(명세서 최선순위) · 임차인 · 세금 교부청구 문건
    tb = tax_before_tenant(
        [Tenant(move_in_date=t["move_in_date"], fixed_date=t["fixed_date"],
                deposit_krw=t["deposit_krw"], has_lease_registration=bool(t["has_lease_registration"]))
         for t in tenants],
        base_date_of((spec or {}).get("base")),
        [e["event_date"] for e in events if e["category"] == "세금 교부청구" and e["event_date"]],
    ).value  # fmt: skip
    if tb:
        sf["tax_before_tenant"] = tb
    spec_note = sf.pop("spec_note", "")
    if spec_note:
        facts["note"] = f"{facts.get('note') or ''} {spec_note}".strip()
    for k, v in sf.items():
        facts[k] = facts.get(k) or v
    bldg = load_building(cur, item, today)  # 건축물대장: 사용승인·그 층 용도(근생빌라 확정)
    if bldg:
        facts.update(
            villa_by_register=bldg["villa"], floor_uses=bldg["unit_floor_uses"], as_of=today,
            use_approval_date=date.fromisoformat(bldg["approved"]) if bldg["approved"] else None,
        )  # fmt: skip
    land = load_land_value(cur, item, bldg, today, land_table)
    redev = find_zone(cur, item)  # 서울 정비사업(지번·단지 이름이 맞을 때만)
    # 정비구역 안인지(11/14): 감정평가 요항 글 → 없으면 필지 토지이용계획(브이월드, land_use 수집기)
    plan_z = af.get("plan_zone") or load_parcel_zone(cur, item)
    if not redev and plan_z == "zone":
        # 토지 이용 계획에 「정비구역」(11/14) — 가까운 구역을 이어 단계를 알고, 못 이으면 구역 안이라는 것만
        redev = near_zone(cur, item_id) or {
            "name": None, "biz_type": None, "stage": None, "how": "토지 이용 계획"}  # fmt: skip
    if redev:
        facts["in_redev_zone"] = redev
        if cash_tables:  # 규제지역(투기과열지구)이면 낙찰자 조합원 자격까지 가름(REDEV-01)
            facts["regulated_area"] = (
                area_class(item.get("sido"), item.get("address"), cash_tables["regulated_areas"])
                == "regulated"
            )
    if market:
        facts.update(
            market_price_krw=market["price_krw"], appraisal_krw=item["appraisal_krw"], as_of=today
        )
    sig = signals(facts)
    eff_failed = effective_failed(
        item["failed_count"], item["appraisal_krw"], item["min_price_krw"]
    )
    rates = rate_range(
        sales, as_of=today, sido=item["sido"], sigungu=item["sigungu"], usage_name=item["usage_name"],
        area_m2=float(item["building_area_m2"]) if item["building_area_m2"] else None, failed_count=eff_failed,
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
        "new_item": new_item(eff_failed, app, market["price_krw"] if market else None).value,
        "market": market,
        # 같은 단지 거래가 없는 단독·다가구: 땅값 역산 추정 시세(하단·가운데·상단, LAND-01) — 보기용, 입찰가 셈에는 안 씀
        "land_value": land,
        "tenant_count": len(tenants),
        # 최저가에 낙찰받을 때 필요한 현금(집 수별) — 찾기·추천의 「가진 현금」 기준(11/9)
        "cash_need": _cash_need(item, market, cash_tables),
        "redev": redev,
        "plan_zone": plan_z,
        "building": bldg,
        "parts": parts or None,
        # 감정평가에서 읽은 것(추천 실거주 점수 · 화면 표시) — 글 자체는 API 가 원문에서 가려 보여 줌
        "appraisal": {
            k: af[k]
            for k in (
                "near_station",
                "near_school",
                "overcrowded",
                "land_permit_area",
                "road_max_m",
            )
            if k in af
        }
        | {
            "firm": apr["firm"],
            "price_date": apr["price_date"].isoformat() if apr["price_date"] else None,
        }
        if points or apr["price_date"]
        else None,
    }
    h = _hash({"facts": facts, "rates": rates.value, "court": court.value, "peers": peers.value,
               "tenants": tenants, "market": market, "building": bldg, "parts": parts, "land": land,
               "engine": ENGINE_VERSION})  # fmt: skip
    last = cur.execute(
        "select version, input_hash from analysis.item_analysis where item_id = %s order by version desc limit 1",
        (item_id,),
    ).fetchone()
    if last and last["input_hash"] == h:
        # 결과는 같아도 「확인한 시각」은 올려 둠 → --stale 이 같은 물건을 매일 다시 고르지 않게
        cur.execute(
            "update analysis.item_analysis set computed_at = now() where item_id = %s and version = %s",
            (item_id, last["version"]),
        )
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
    # 관리자가 판단한 신호(11/2): 「없음」은 빼고 「확정」은 확정으로 — 다시 분석해도 유지
    cur.execute(
        """delete from analysis.risk_signals s using analysis.signal_overrides o
           where s.item_id = %s and o.item_id = s.item_id and o.rule_id = s.rule_id and o.status = '없음'""",
        (item_id,),
    )
    cur.execute(
        """update analysis.risk_signals s set status = '확정' from analysis.signal_overrides o
           where s.item_id = %s and o.item_id = s.item_id and o.rule_id = s.rule_id and o.status = '확정'""",
        (item_id,),
    )
    for kind, ok in [("item", True), ("status_report", has_sr), ("deliveries", bool(events)),
                     ("building", bool(bldg))]:  # fmt: skip
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


def load_cash_tables(conn: psycopg.Connection, today: date) -> dict[str, Any] | None:
    """「필요한 현금」 셈에 쓰는 기준표(대출 비율·취득세·규제지역). 하나라도 없으면 None(셈 안 함)."""
    out: dict[str, Any] = {}
    for k in CASH_TABLE_KEYS:
        row = conn.execute(
            "select value from ref.rule_tables where rule_key = %s and valid_from <= %s"
            " order by valid_from desc limit 1",
            (k, today),
        ).fetchone()
        if not row:
            return None
        out[k] = row[0]
    return out


def _cash_need(
    item: dict[str, Any], market: dict[str, Any] | None, tables: dict[str, Any] | None
) -> dict[str, int] | None:
    if not tables or not item.get("min_price_krw"):
        return None
    try:
        return cash_at_min(
            min_price_krw=item["min_price_krw"], appraisal_krw=item.get("appraisal_krw"),
            market_krw=(market or {}).get("price_krw"),
            area_m2=float(item["building_area_m2"]) if item.get("building_area_m2") else None,
            sido=item.get("sido"), address=item.get("address"), tables=tables,
        )  # fmt: skip
    except Exception:  # noqa: BLE001 — 기준표 모양이 바뀌어도 분석은 계속(이 칸만 비움)
        return None


# 분석이 없거나, 그 뒤로 물건·서류가 바뀌었거나, 규칙 버전이 바뀐 물건(11/9 — 버전은 안 봐서
# 규칙을 고쳐도 대부분 물건이 예전 셈으로 남았음)
STALE_SQL = """
select i.item_id from core.items i
left join lateral (select computed_at, engine_version from analysis.item_analysis x
                   where x.item_id = i.item_id order by version desc limit 1) a on true
where i.sale_date >= %s
  and (a.computed_at is null or a.engine_version is distinct from %s or i.updated_at > a.computed_at
       or exists (select 1 from raw.court_doc_raw d where d.case_id = i.case_id and d.fetched_at > a.computed_at))
order by i.sale_date
"""


def sigungu_from_address(address: str | None) -> str | None:
    """「경기 용인시 수지구 …」 → 용인시, 「서울 강남구 …」 → 강남구."""
    parts = (address or "").split()
    if len(parts) > 1 and parts[1][-1:] in ("시", "군", "구"):
        return parts[1]
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--item")
    ap.add_argument("--stale", action="store_true", help="분석이 없거나 그 뒤로 바뀐 물건만")
    a = ap.parse_args()
    today = date.today()
    with connect() as lock:
        # 아침 묶음과 「관심 바로 준비」가 같은 때 분석을 돌리면 서로 겹침(11/2) → 하나만 돌고 나머지는 건너뜀
        if not a.item and not lock.execute("select pg_try_advisory_lock(7421001)").fetchone()[0]:  # type: ignore[index]
            print("다른 분석이 도는 중이라 건너뜀")
            return
        _analyze(a, today)


def _analyze(a: argparse.Namespace, today: date) -> None:
    with connect() as conn, run(conn, "analyze", "물건 분석") as job:
        sales = load_sales(conn, today)
        row = conn.execute(
            "select value from ref.rule_tables where rule_key = 'commercial_lease_limit' and valid_from <= %s"
            " order by valid_from desc limit 1",
            (today,),
        ).fetchone()
        commercial_table = row[0] if row else None
        cash_tables = load_cash_tables(conn, today)
        lv = conn.execute(
            "select value from ref.rule_tables where rule_key = 'land_value' and valid_from <= %s"
            " order by valid_from desc limit 1",
            (today,),
        ).fetchone()
        land_table = lv[0] if lv else None
        if a.item:
            ids = [a.item]
        elif a.stale:
            ids = [
                r[0]
                for r in conn.execute(
                    STALE_SQL, (today - timedelta(days=7), ENGINE_VERSION)
                ).fetchall()
            ]
        else:
            ids = [r[0] for r in conn.execute(
                "select item_id from core.items where sale_date >= %s", (today - timedelta(days=7),)).fetchall()]  # fmt: skip
        for item_id in ids:
            if analyze_item(conn, item_id, sales, today, commercial_table, cash_tables, land_table):
                job.count += 1
            conn.commit()
    print(f"분석 {job.count:,}건 (대상 {len(ids):,})")


if __name__ == "__main__":
    main()
