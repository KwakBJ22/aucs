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
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

import psycopg
from aucs_rules import ENGINE_VERSION
from aucs_rules.appraisal_parts import appraisal_parts
from aucs_rules.appraisal_points import (
    appraisal_facts,
    land_plan_of_parcel,
    parcel_facts,
    parse_points,
    plan_zone_of_parcel,
)
from aucs_rules.area_stats import area_stats
from aucs_rules.building import lot_key, parse_jibun, summarize
from aucs_rules.calc import CASH_TABLE_KEYS, area_class, cash_at_min, usage_for_kind
from aucs_rules.costs import commercial_over_limit
from aucs_rules.land_value import HouseTrade, land_value
from aucs_rules.nearby import JIMOK, land_trade_price, nearby_stores
from aucs_rules.price import Trade, is_under, market_price, nearby_price, trade_region
from aucs_rules.progress import judge_progress
from aucs_rules.risk import is_land_or_house, signals, top_signal
from aucs_rules.rule_dates import change_line
from aucs_rules.rule_dates import plan as rule_plan
from aucs_rules.sale_rate import (
    Sale,
    court_cell,
    effective_failed,
    local_peers,
    new_item,
    rate_range,
)
from aucs_rules.small_lease_region import region_class
from aucs_rules.spec_facts import note_facts, spec_facts
from aucs_rules.tenants import (
    Tenant,
    base_date_of,
    base_dates_of,
    power_tenants,
    tax_before_tenant,
    tenant_doubts,
)
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from aucs_workers.collectors.official_prices import pnu_of
from aucs_workers.db import connect
from aucs_workers.jobs.redev_match import find_zone, load_zones, near_zone
from aucs_workers.jobs.runlog import run

COMMERCIAL_WORDS = ("상가", "근린", "점포", "사무실", "공장")


_LAND_USE_TABLE: list[bool] = []  # 표가 있는지 한 번만 봄
RuleRows = dict[str, list[tuple[date, Any]]]  # 기준표 줄(시행일 · 값), 물건마다 잔금일로 고름
CHUNK = 100  # 재료를 한 번에 받아 둘 물건 수
COMMIT_EVERY = 20


@dataclass
class Pre:
    """물건 여러 개의 재료를 한꺼번에 받아 둔 것(11/14).

    예전에는 물건마다 조회를 10번쯤 따로 보내, 전체를 다시 분석하면 70분이 걸렸음(물건 하나에 0.2초 — 거의 다 오가는 시간).
    받는 칸 · 줄 모양은 물건마다 받던 것과 같게 둠(같은 재료면 같은 결과 — input_hash 가 안 바뀜).
    """

    items: dict[str, dict[str, Any]] = field(default_factory=dict)
    events: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    tenants: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    status_reports: set[str] = field(default_factory=set)
    possession: dict[str, str] = field(
        default_factory=dict
    )  # 사건 → 현황조사서 점유 관계 글(가짜 임차인 의심)
    docs: dict[tuple[str, str], Any] = field(
        default_factory=dict
    )  # (사건, 서류 종류) → 가장 최근 원문
    trades: dict[tuple[str, str, str], list[tuple[Any, ...]]] = field(default_factory=dict)
    # (법정동, 종류) → 최근 1년 매매(주변 비슷한 집, 11/24)
    near: dict[tuple[str, str], list[tuple[Any, ...]]] = field(default_factory=dict)
    buildings: dict[tuple[str, str], list[dict[str, Any]]] = field(default_factory=dict)
    parcels: dict[str, Any] | None = None  # 필지 번호 → 걸린 지역 · 지구(표가 없으면 None)
    overrides: set[str] = field(default_factory=set)  # 관리자가 판단한 신호가 있는 물건
    zones: dict[tuple[str, str], list[dict[str, Any]]] | None = None  # 서울 정비구역(구 · 동)
    units: dict[str, dict[str, Any]] = field(default_factory=dict)  # 물건 → 그 호 전유공용(11/16)
    complexes: dict[str, dict[str, Any]] = field(default_factory=dict)  # 필지번호 → 단지(11/16)
    stores: dict[str, dict[str, Any]] = field(default_factory=dict)  # 물건 → 주변 가게(11/16)
    land_trades: dict[str, list[dict[str, Any]]] = field(default_factory=dict)  # 읍면동 8자리 → 땅 거래


def _market_key(item: dict[str, Any]) -> tuple[str, str, str] | None:
    kind = trade_type(item.get("usage_name"), item.get("building_desc"))
    if not kind or not item.get("building_area_m2") or not item.get("region_code") or not item.get("lot_no"):  # fmt: skip
        return None
    return trade_region(item["region_code"]), kind, item["lot_no"]


def _building_key(item: dict[str, Any]) -> tuple[str, str] | None:
    p = parse_jibun(item.get("lot_no"))
    if not p or not item.get("region_code"):
        return None
    return item["region_code"], lot_key(*p)


_AREA_STATS: list[Any] = []


def load_area_stats(cur: Any) -> Any:
    """지역 평균 통계(R-ONE, collectors/rone)를 한 번만 받아 둠 — 표가 없으면(이주 0060 전) None."""
    if not _AREA_STATS:
        out: dict[str, dict[str, dict[str, Any]]] | None = None
        if cur.execute("select to_regclass('ref.region_stats') is not null as ok").fetchone()["ok"]:
            out = {}
            for r in cur.execute(
                "select stat_key, region, period, value, unit from ref.region_stats"
            ).fetchall():
                out.setdefault(r["stat_key"], {})[r["region"]] = r
        _AREA_STATS.append(out)
    return _AREA_STATS[0]


def _land_use_ready(cur: Any) -> bool:
    """필지 토지이용계획 표가 있는지 한 번만 봄(이주 0048 을 넣기 전에도 분석이 멈추지 않게)."""
    if not _LAND_USE_TABLE:
        row = cur.execute("select to_regclass('core.parcel_land_use') is not null as ok").fetchone()
        _LAND_USE_TABLE.append(bool(row and row["ok"]))
    return _LAND_USE_TABLE[0]


def preload(
    conn: psycopg.Connection,
    ids: list[str],
    today: date,
    zones: dict[tuple[str, str], list[dict[str, Any]]] | None = None,
) -> Pre:
    """물건 묶음의 재료를 조회 9번으로 받음(물건마다 10번 → 묶음마다 9번)."""
    cur = conn.cursor(row_factory=dict_row)
    pre = Pre(zones=zones)
    for r in cur.execute("select * from core.items where item_id = any(%s)", (ids,)).fetchall():
        pre.items[r["item_id"]] = r
    cases = sorted({r["case_id"] for r in pre.items.values()})
    for r in cur.execute(
        "select case_id, event_date, category, after_deadline, text_masked as text from core.case_events where case_id = any(%s)",
        (cases,),
    ).fetchall():
        pre.events.setdefault(r.pop("case_id"), []).append(r)
    for r in cur.execute(
        "select case_id, item_id, move_in_date, fixed_date, claim_date, deposit_krw, monthly_rent_krw, has_lease_registration"
        " from core.tenants where case_id = any(%s)",
        (cases,),
    ).fetchall():
        pre.tenants.setdefault(r.pop("case_id"), []).append(r)
    for r in cur.execute(
        """select distinct on (case_id) case_id, (select string_agg(coalesce(o->>'gdsPossCtt', ''), ' ') from jsonb_array_elements(coalesce(payload->'dlt_ordTsRlet', '[]'::jsonb)) o) as poss from raw.court_doc_raw
           where case_id = any(%s) and doc_kind = 'status_report' order by case_id, fetched_at desc""",
        (cases,),
    ).fetchall():
        pre.status_reports.add(r["case_id"])
        pre.possession[r["case_id"]] = r["poss"] or ""
    for r in cur.execute(
        """select distinct on (case_id, doc_kind) case_id, doc_kind, payload from raw.court_doc_raw
           where case_id = any(%s) and ((left(doc_kind, 12) = 'item_detail_' and jsonb_typeof(payload->'dma_result') = 'object')  -- 빈 답은 건너뜀(11/25)
                                      or doc_kind in ('appraisal', 'appraisal_pdf'))
           order by case_id, doc_kind, fetched_at desc""",
        (cases,),
    ).fetchall():
        pre.docs[(r["case_id"], r["doc_kind"])] = r["payload"]
    mk = sorted({k for i in pre.items.values() if (k := _market_key(i))})
    if mk:
        for r in cur.execute(
            """select region_code, prop_type, lot_no, deal_date, price_krw, area_m2, floor, build_year
               from core.trades
               where (region_code, lot_no) in (select * from unnest(%s::text[], %s::text[]))
                 and deal_kind = 'sale' and deal_date >= %s and price_krw > 0""",
            ([k[0] for k in mk], [k[2] for k in mk], today - timedelta(days=730)),
        ).fetchall():
            pre.trades.setdefault((r["region_code"], r["prop_type"], r["lot_no"]), []).append(
                (r["deal_date"], r["price_krw"], r["area_m2"], r["floor"], r["build_year"])
            )
        nk = sorted({(k[0], k[1]) for k in mk})
        for r in cur.execute(
            NEAR_SQL
            + " and (region_code, prop_type) in (select * from unnest(%s::text[], %s::text[]))",
            (today - timedelta(days=365), [k[0] for k in nk], [k[1] for k in nk]),
        ).fetchall():
            pre.near.setdefault((r["region_code"], r["prop_type"]), []).append(
                (r["deal_date"], r["price_krw"], r["area_m2"], r["lot_no"], r["build_year"])
            )
    bk = sorted({k for i in pre.items.values() if (k := _building_key(i))})
    if bk:
        for r in cur.execute(
            """select region_code, lot_no, kind, data from core.building_register
               where (region_code, lot_no) in (select * from unnest(%s::text[], %s::text[]))
               order by region_code, lot_no, kind, seq""",
            ([k[0] for k in bk], [k[1] for k in bk]),
        ).fetchall():
            pre.buildings.setdefault((r["region_code"], r["lot_no"]), []).append(
                {"kind": r["kind"], "data": r["data"]}
            )
    if _land_use_ready(cur):
        pnus = sorted(
            {
                p
                for i in pre.items.values()
                if (p := pnu_of(i.get("region_code") or "", i.get("lot_no") or ""))
            }
        )
        pre.parcels = {
            r["pnu"]: r["uses"]
            for r in cur.execute(
                "select pnu, uses from core.parcel_land_use where pnu = any(%s)", (pnus,)
            ).fetchall()
        }
    if _table_ready(cur, "core.building_units"):
        pre.units = {r["item_id"]: r for r in cur.execute(UNIT_SQL + " where item_id = any(%s)", (ids,)).fetchall()}  # fmt: skip
    if _table_ready(cur, "ref.complexes"):
        pn = sorted({p for i in pre.items.values() if (p := pnu_of(i.get("region_code") or "", i.get("lot_no") or ""))})  # fmt: skip
        for r in cur.execute(COMPLEX_SQL + " where pnu = any(%s) order by pnu, unit_cnt desc nulls last", (pn,)).fetchall():  # fmt: skip
            pre.complexes.setdefault(r["pnu"], r)  # 한 필지에 단지가 여럿이면 세대가 많은 것
    if _table_ready(cur, "core.item_stores"):
        pre.stores = {r["item_id"]: r for r in cur.execute("select * from core.item_stores where item_id = any(%s)", (ids,)).fetchall()}  # fmt: skip
    dongs = sorted({i["region_code"][:8] for i in pre.items.values() if (i.get("usage_name") or "") in JIMOK and i.get("region_code")})  # fmt: skip
    if dongs:
        for r in cur.execute(LAND_SQL + " and left(region_code, 8) = any(%s)", (today - timedelta(days=730), dongs)).fetchall():  # fmt: skip
            pre.land_trades.setdefault(r["dong"], []).append(r)
    pre.overrides = {
        r["item_id"]
        for r in cur.execute(
            "select distinct item_id from analysis.signal_overrides where item_id = any(%s)", (ids,)
        ).fetchall()
    }
    return pre


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


# 같은 지번인데 다른 종류로 신고된 거래(11/21 대표님 「작업해」): 대장은 아파트인데 실거래는 연립다세대로
# (또는 그 반대) 신고된 작은 건물 — 같은 건물이라 그 종류 거래가 없을 때만 씀. 진행 물건 중 아파트 33 · 빌라 91건.
OTHER_KIND = {"apt": "rowhouse", "rowhouse": "apt"}


def load_market(
    conn: psycopg.Connection, item: dict[str, Any], today: date, pre: Pre | None = None
) -> dict[str, Any] | None:
    """같은 법정동·같은 지번(같은 단지·건물)의 최근 24개월 매매로 시세. 전용 ±3㎡.
    그 종류 거래가 없으면 같은 지번의 다른 종류(아파트 ↔ 연립다세대) 거래로."""
    kind = trade_type(item.get("usage_name"), item.get("building_desc"))
    area = item.get("building_area_m2")
    if not kind or not area or not item.get("region_code") or not item.get("lot_no"):
        return None
    region = trade_region(item["region_code"])

    def get(k: str) -> list[Any]:
        if pre is not None:
            return pre.trades.get((region, k, item["lot_no"]), [])
        return conn.execute(
            """select deal_date, price_krw, area_m2, floor, build_year from core.trades
               where region_code = %s and prop_type = %s and deal_kind = 'sale' and lot_no = %s
                 and deal_date >= %s and price_krw > 0""",
            (region, k, item["lot_no"], today - timedelta(days=730)),
        ).fetchall()

    rows, other = get(kind), None
    if not rows and kind in OTHER_KIND:
        other = OTHER_KIND[kind]
        rows = get(other)
    lot = item["lot_no"]
    trades = [Trade(r[0], int(r[1]), float(r[2]), r[3], lot, r[4]) for r in rows]
    res = market_price(
        trades, as_of=today, complex_name=lot, area_m2=float(area), under=is_under(item.get("building_desc"))
    )
    if res.value is None:
        return None
    recent = sorted(res.evidence, key=lambda e: e["date"], reverse=True)[:5]
    return {**res.value, "recent": recent} | ({"other_kind": other} if other else {})


NEAR_SQL = """select region_code, prop_type, lot_no, deal_date, price_krw, area_m2, build_year
  from core.trades where deal_kind = 'sale' and deal_date >= %s and price_krw > 0 and area_m2 > 0"""


def load_near_market(
    cur: Any, item: dict[str, Any], market: dict[str, Any] | None, bldg: dict[str, Any] | None,
    today: date, pre: Pre | None = None,
) -> dict[str, Any] | None:  # fmt: skip
    """같은 건물 거래가 1년 3건 미만일 때 같은 법정동 비슷한 집(전용 ±10% · 지은 해 ±5년 · 1년)으로 어림한 값.
    화면에 같은 건물 값과 나란히 보이기만 함 — 입찰가 계산에는 안 씀(11/24 대표님 ①, 57221: 같은 건물 1건뿐)."""
    if market and market.get("level") == 1:
        return None
    key = _market_key(item)
    if not key:
        return None
    region, kind, _ = key
    if pre is not None:
        rows = pre.near.get((region, kind), [])
    else:
        rows = cur.execute(
            NEAR_SQL + " and region_code = %s and prop_type = %s",
            (today - timedelta(days=365), region, kind),
        ).fetchall()
        rows = [
            (x["deal_date"], x["price_krw"], x["area_m2"], x["lot_no"], x["build_year"])
            for x in rows
        ]
    approved = (bldg or {}).get("approved")
    trades = [Trade(d, int(p), float(a), None, lot, by) for d, p, a, lot, by in rows]
    res = nearby_price(
        trades, as_of=today, area_m2=float(item["building_area_m2"]),
        build_year=int(approved[:4]) if approved else None,
    )  # fmt: skip
    return res.value


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


def load_detail(cur: Any, item: dict[str, Any], pre: Pre | None = None) -> dict[str, Any]:
    """물건상세(item_detail_N) 원문의 dma_result — 명세서 칸 · 감정평가 요항을 함께 읽으려고 한 번만 부름."""
    kind = f"item_detail_{item.get('item_no') or 1}"
    if pre is not None:
        return dict((pre.docs.get((item["case_id"], kind)) or {}).get("dma_result") or {})
    row = cur.execute(
        "select payload from raw.court_doc_raw where case_id = %s and doc_kind = %s"
        " and jsonb_typeof(payload->'dma_result') = 'object' order by fetched_at desc limit 1",
        (item["case_id"], kind),
    ).fetchone()
    return dict(((row or {}).get("payload") or {}).get("dma_result") or {})


def load_appraisal(cur: Any, item: dict[str, Any], pre: Pre | None = None) -> dict[str, Any]:
    """감정평가서 정보(raw 'appraisal' — 가격시점·작성일)와 원본에서 읽은 회사 이름(raw 'appraisal_pdf'), 11/4."""
    if pre is not None:
        by = {
            k: pre.docs.get((item["case_id"], k)) or {}
            for k in ("appraisal", "appraisal_pdf")
            if (item["case_id"], k) in pre.docs
        }
    else:
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
    case_tenants: bool | None = None,
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
        "rehab_resumed": rehab_resumed(events),
        "duplicate_auction": "중복경매" in cats,
        "stop_attempts": progress.value == "기일이 바뀔 수 있음",
        "creditor_changed": "채권자 바뀜" in cats,
        "claim_after_deadline": any(e["after_deadline"] for e in events),
        "commercial_over_limit": commercial_over_limit,
        **({"tenants_checked": False} if not has_status_report else {}),
        # 문건 임차인은 호를 몰라, 사건 현황조사서에 임차인이 하나도 없을 때만(다른 호 임차인을 이 호에 붙이지 않음)
        **(
            {"doc_tenants": dt}
            if not (tenants if case_tenants is None else case_tenants) and (dt := doc_tenants(events))
            else {}
        ),
    }


def rehab_resumed(events: list[dict[str, Any]]) -> bool:
    """회생 · 파산 문건 뒤에 속행 신청이나 입찰이 있었나(11/24 수원 2025타경57005 — 파산선고 뒤 속행 · 두 번 매각)."""
    last = max((e["event_date"] for e in events if e["category"] == "회생·파산" and e["event_date"]), default=None)
    return bool(last) and any(
        e["event_date"] and e["event_date"] > last and e["category"] in ("경매 속행 신청", "입찰 진행")
        for e in events
    )


# 이름 뒤 괄호(「한OO(OO)」 — 같은 사람)는 떼고 셈(11/24 인천 2025타경513908: 2명을 3명으로 셌음)
_DOC_TENANT = re.compile(r"^\s*(?:주택|상가)?임차(권자|인)\s+([^\s(]+)")


def doc_tenants(events: list[dict[str, Any]]) -> dict[str, Any] | None:
    """문건 · 송달에 이름이 나온 임차인 · 임차권자(가린 이름 기준). 없으면 None."""
    who: dict[str, str] = {}
    for e in events:
        if m := _DOC_TENANT.match(e.get("text") or ""):
            lease = m.group(1) == "권자" and who.get(m.group(2)) != "tenant"
            who[m.group(2)] = "lease" if lease else "tenant"
    if not who:
        return None
    return {"n": len(who), "lease_only": all(v == "lease" for v in who.values())}


HOUSE_USES = ("단독주택다가구", "단독주택", "다가구주택")
HOUSE_MAIN = re.compile(r"단독|다가구|다중주택")


def load_land_value(
    cur: Any, item: dict[str, Any], bldg: dict[str, Any] | None, today: date,
    table: dict[str, Any] | None,
) -> dict[str, Any] | None:  # fmt: skip
    """단독·다가구: 같은 동 실거래로 땅값을 역산해 추정 시세 하단·가운데·상단(LAND-01). 지분 물건은 뺌."""
    if not table or not bldg or item.get("is_share") or not item.get("region_code"):
        return None
    if item.get("usage_name") not in HOUSE_USES and not HOUSE_MAIN.search(
        bldg.get("main_use") or ""
    ):
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


_TABLES: dict[str, bool] = {}
UNIT_SQL = "select item_id, result, own_area, common_area, own_use, own_use_etc from core.building_units"
COMPLEX_SQL = "select pnu, names, unit_cnt, dong_cnt, max_floors from ref.complexes"


def _table_ready(cur: Any, name: str) -> bool:
    """새 표(이주 0061 · 0062)가 있는지 한 번만 봄 — 없어도 분석이 멈추지 않게."""
    if name not in _TABLES:
        row = cur.execute("select to_regclass(%s) is not null as ok", (name,)).fetchone()
        _TABLES[name] = bool(row and row["ok"])
    return _TABLES[name]


LAND_SQL = """select left(region_code, 8) as dong, deal_date, price_krw, land_area_m2, sub_type, contract_kind
  from core.trades where prop_type = 'land' and deal_kind = 'sale' and deal_date >= %s"""


def load_nearby(cur: Any, item: dict[str, Any], zones: list[str] | None, today: date, pre: Pre | None = None) -> tuple[Any, Any]:  # fmt: skip
    """상가 주변 가게 · 같은 동 땅 거래(11/16). 없으면 None."""
    usage, code = item.get("usage_name") or "", (item.get("region_code") or "")[:8]
    if pre is not None:
        row, trades = pre.stores.get(item["item_id"]), pre.land_trades.get(code, [])
    else:
        row = None
        if _table_ready(cur, "core.item_stores"):
            row = cur.execute("select * from core.item_stores where item_id = %s", (item["item_id"],)).fetchone()  # fmt: skip
        trades = []
        if usage in JIMOK and code:
            trades = cur.execute(LAND_SQL + " and left(region_code, 8) = %s", (today - timedelta(days=730), code)).fetchall()  # fmt: skip
    return nearby_stores(row), land_trade_price(usage, zones, trades, today) if trades else None


def load_unit_complex(
    cur: Any, item: dict[str, Any], pre: Pre | None = None
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """그 호의 전유공용면적 · 단지 식별정보(11/16). 없으면 None."""
    pnu = pnu_of(item.get("region_code") or "", item.get("lot_no") or "")
    if pre is not None:
        return pre.units.get(item["item_id"]), pre.complexes.get(pnu or "")
    unit = cx = None
    if _table_ready(cur, "core.building_units"):
        unit = cur.execute(UNIT_SQL + " where item_id = %s", (item["item_id"],)).fetchone()
    if pnu and _table_ready(cur, "ref.complexes"):
        cx = cur.execute(COMPLEX_SQL + " where pnu = %s order by unit_cnt desc nulls last limit 1", (pnu,)).fetchone()  # fmt: skip
    return unit, cx


def load_building(
    cur: Any, item: dict[str, Any], today: date, pre: Pre | None = None
) -> dict[str, Any] | None:
    """건축물대장(collectors/buildings) → 요약. 지번을 못 읽거나 아직 안 받았으면 None."""
    key = _building_key(item)
    if not key:
        return None
    if pre is not None:
        rows = pre.buildings.get(key, [])
    else:
        rows = cur.execute(
            "select kind, data from core.building_register where region_code = %s and lot_no = %s order by kind, seq",
            key,
        ).fetchall()
    titles = [r["data"] for r in rows if r["kind"] == "title"]
    floors = [r["data"] for r in rows if r["kind"] == "floor"]
    usage = f"{item.get('usage_name') or ''} {item.get('building_desc') or ''}"
    unit, cx = load_unit_complex(cur, item, pre)
    return summarize(titles, floors, item.get("address"), usage, today, unit, cx)


def load_parcel_uses(cur: Any, item: dict[str, Any], pre: Pre | None = None) -> Any:
    """필지 토지이용계획(collectors/land_use)에 걸린 지역 · 지구 목록. 아직 안 받았으면 None."""
    pnu = pnu_of(item.get("region_code") or "", item.get("lot_no") or "")
    if pre is not None:
        return (pre.parcels or {}).get(pnu) if pnu else None
    if not _land_use_ready(cur) or not pnu:
        return None
    row = cur.execute("select uses from core.parcel_land_use where pnu = %s", (pnu,)).fetchone()
    return row["uses"] if row else None


def load_parcel_zone(cur: Any, item: dict[str, Any], pre: Pre | None = None) -> str | None:
    """필지 토지이용계획 → 'zone' / 'district' / 'planned'. 아직 안 받았으면 None."""
    uses = load_parcel_uses(cur, item, pre)
    return plan_zone_of_parcel(uses) if uses is not None else None


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
    pre: Pre | None = None,
    cash_rows: RuleRows | None = None,
) -> bool:
    """pre 가 있으면 재료를 거기서 꺼내 씀(묶음으로 미리 받은 것), 없으면 예전처럼 물건마다 조회."""
    cur = conn.cursor(row_factory=dict_row)
    if pre is not None:
        item = pre.items.get(item_id)
    else:
        item = cur.execute("select * from core.items where item_id = %s", (item_id,)).fetchone()
    if not item:
        return False
    if pre is not None:
        events = pre.events.get(item["case_id"], [])
        tenants = pre.tenants.get(item["case_id"], [])
        has_sr = item["case_id"] in pre.status_reports
        poss = pre.possession.get(item["case_id"], "")
    else:
        events = cur.execute(
            "select event_date, category, after_deadline, text_masked as text from core.case_events where case_id = %s",
            (item["case_id"],),
        ).fetchall()
        tenants = cur.execute(
            "select item_id, move_in_date, fixed_date, claim_date, deposit_krw, monthly_rent_krw, has_lease_registration from core.tenants where case_id = %s",
            (item["case_id"],),
        ).fetchall()
        sr = cur.execute(
            """select (select string_agg(coalesce(o->>'gdsPossCtt', ''), ' ') from jsonb_array_elements(coalesce(payload->'dlt_ordTsRlet', '[]'::jsonb)) o) as poss from raw.court_doc_raw
               where case_id = %s and doc_kind = 'status_report' order by fetched_at desc limit 1""",
            (item["case_id"],),
        ).fetchone()
        has_sr, poss = sr is not None, (sr or {}).get("poss") or ""
    # 그 호 임차인만(호를 모르는 줄은 사건 전체로 — 11/24 수원 2025타경57005)
    case_tenants = bool(tenants)
    tenants = [
        {k: v for k, v in t.items() if k != "item_id"}
        for t in tenants
        if t.get("item_id") in (None, item["item_id"])
    ]
    detail = load_detail(cur, item, pre)
    # 감정평가 요항(11/4 사용 허락): 화면 요점 + 맹지·좁은 길·개발제한·교육환경·토지거래허가·과밀억제 사실
    # 법원 요항을 아직 못 받았으면 받아 둔 감정평가서 원본의 요항표로(11/11)
    apr = load_appraisal(cur, item, pre)
    points = parse_points(detail.get("aeeWevlMnpntLst") or apr["points"])
    af = appraisal_facts(points).value
    # 필지 토지이용계획(브이월드)으로도 채움(11/15): 개발제한구역 · 토지거래허가구역 · 과밀억제권역 — 요항 글이 먼저
    uses = load_parcel_uses(cur, item, pre)
    pf = parcel_facts(uses)
    hint = True if pf.get("overcrowded") else (bool(af.get("overcrowded")) if points else None)
    # 감정가 나눔(11/7): 토지·건물 금액 · 제시외 건물 · 대지권 — 원본 없이 물건상세로
    parts = appraisal_parts(
        detail.get("gdsDspslObjctLst"),
        detail.get("gdsNotSugtBldLsstAll"),
        detail.get("rgltLandLstAll"),
    ).value
    over = commercial_over(item, tenants, commercial_table, today, hint)
    market = load_market(conn, item, today, pre)
    facts = build_facts(item, events, tenants, has_sr, over, case_tenants=case_tenants)
    for k, v in (*af.items(), *pf.items()):
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
    # 비고 글(목록 + 명세서)에만 적힌 농취증 · 재매각 · 유치권 · 법정지상권 · 대항력 있는 임차인 · 보증기관 대항력 포기(11/24)
    for k, v in note_facts(facts.get("note"), facts).items():
        facts[k] = facts.get(k) or v
    bldg = load_building(cur, item, today, pre)  # 건축물대장: 사용승인·그 층 용도(근생빌라 확정)
    if bldg:
        facts.update(
            villa_by_register=bldg["villa"], floor_uses=bldg["unit_floor_uses"], as_of=today,
            villa_level=bldg.get("villa_level"), unit_use=bldg.get("unit_use"),
            use_approval_date=date.fromisoformat(bldg["approved"]) if bldg["approved"] else None,
        )  # fmt: skip
    land = load_land_value(cur, item, bldg, today, land_table)
    near_market = load_near_market(cur, item, market, bldg, today, pre)
    redev = find_zone(
        cur, item, pre.zones if pre is not None else None
    )  # 서울 정비사업(지번·단지 이름이 맞을 때만)
    # 정비구역 안인지(11/14): 감정평가 요항 글 → 없으면 필지 토지이용계획(브이월드, land_use 수집기)
    plan_z = af.get("plan_zone") or load_parcel_zone(cur, item, pre)
    # 용도지역 · 도시계획시설(11/15): 같은 토지이용계획에서 — 시설은 땅 · 단독에만 뜻이 있어 그때만 남김
    land_plan = land_plan_of_parcel(uses)
    if land_plan and not is_land_or_house(facts.get("usage_text")):
        land_plan = {**land_plan, "facilities": []} if land_plan["zones"] else None
    if land_plan and land_plan["facilities"]:
        facts["plan_facilities"] = [x["name"] for x in land_plan["facilities"]]
    # 이 지역 평균(11/15): 상가 수익률 · 공실률, 오피스텔 수익률, 전월세전환율 — 보기용
    area = area_stats(item.get("usage_name"), item.get("building_desc"), item.get("sido"),
                      item.get("sigungu"), load_area_stats(cur))  # fmt: skip
    stores, land_trades = load_nearby(cur, item, (land_plan or {}).get("zones"), today, pre)
    if not redev and plan_z == "zone":
        # 토지 이용 계획에 「정비구역」(11/14) — 가까운 구역을 이어 단계를 알고, 못 이으면 구역 안이라는 것만
        redev = near_zone(cur, item_id) or {
            "name": None, "biz_type": None, "stage": None, "how": "토지 이용 계획"}  # fmt: skip
    if redev:
        facts["in_redev_zone"] = redev
        # 규제지역(투기과열지구)이면 낙찰자 조합원 자격까지 가름(REDEV-01) — 서울만.
        # 경기 자료는 기준일이 오래돼(2025. 9.) 단계가 바뀌었을 수 있어 이름 · 단계 · 날짜만 보여 줌(11/16)
        if cash_tables and item.get("sido") == "서울특별시":
            facts["regulated_area"] = (
                area_class(item.get("sido"), item.get("address"), cash_tables["regulated_areas"])
                == "regulated"
            )
    if market:
        facts.update(
            market_price_krw=market["price_krw"], appraisal_krw=item["appraisal_krw"], as_of=today
        )
    # 가짜 임차인 의심(11/15): 문건(무상거주확인서·배당배제) · 근저당보다 앞선 전입 · 보증금 크기 · 현황조사서 점유 글
    base_txt = (spec or {}).get("base") or ""
    doubt = tenant_doubts(
        [Tenant(move_in_date=t["move_in_date"], fixed_date=t["fixed_date"], claim_date=t.get("claim_date"),
                deposit_krw=t["deposit_krw"]) for t in tenants],
        base_date_of(base_txt), "근저당" in base_txt, [e.get("text") or "" for e in events], poss,
        (market or {}).get("price_krw") or item.get("appraisal_krw"),
    ).value  # fmt: skip
    if doubt:
        facts["tenant_doubt"] = doubt
    # 말소기준보다 먼저 전입한 임차인(11/25 점검 — 명세서 비고에 「인수」가 없으면 신호가 없었음, 진행 98건)
    ts = [Tenant(move_in_date=t["move_in_date"], fixed_date=t["fixed_date"], claim_date=t.get("claim_date"),
                 deposit_krw=t["deposit_krw"], has_lease_registration=bool(t["has_lease_registration"]))
          for t in tenants]  # fmt: skip
    # 11/25: 목록마다 말소기준이 다르면(여러 필지 · 건물) 가장 이른 날보다 먼저면 확실, 늦은 날보다만 먼저면 「확인」
    bases = sorted(set(base_dates_of(base_txt)))
    tp = power_tenants(ts, bases[0] if bases else None)
    if not tp and len(bases) > 1 and (tp := power_tenants(ts, bases[-1])):
        tp = {**tp, "multi_base": True}
    if tp:
        facts["tenant_power"] = tp
    sig = signals(facts)
    # 법원 유찰 횟수가 아니라 지금 최저가가 감정가에서 몇 번 내린 값인가(0077, 11/24)
    eff_failed = effective_failed(
        item["failed_count"], item["appraisal_krw"], item["min_price_krw"], item.get("price_round")
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
    cash_need, law_change, rules_used = _cash_plan(item, market, cash_tables, bldg, cash_rows, today)
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
        # 같은 건물 거래가 적을 때 주변 비슷한 집 어림(보기용 · 입찰가 셈에 안 씀, 11/24)
        "near_market": near_market,
        # 같은 단지 거래가 없는 단독·다가구: 땅값 역산 추정 시세(하단·가운데·상단, LAND-01) — 보기용, 입찰가 셈에는 안 씀
        "land_value": land,
        "tenant_count": len(tenants),
        # 최저가에 낙찰받을 때 필요한 현금(집 수별) — 찾기·추천의 「가진 현금」 기준(11/9)
        "cash_need": cash_need,
        # 잔금 기간에 기준표(세율 · 대출 비율 · 규제지역)가 바뀌면 한 줄(11/25) — 금액이 달라질 때만
        "law_change": law_change,
        "rules_used": rules_used,
        "redev": redev,
        "plan_zone": plan_z,
        "land_plan": land_plan,
        "area_stats": area,
        "nearby_stores": stores,
        "land_trades": land_trades,
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
               "tenants": tenants, "market": market, "near_market": near_market, "building": bldg, "parts": parts, "land": land,
               "area": area, "stores": stores, "land_trades": land_trades, "engine": ENGINE_VERSION,
               "rules": rules_used})  # fmt: skip
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
    if pre is None or item_id in pre.overrides:  # 판단한 신호가 없는 물건은 건너뜀
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
    cur.executemany(  # 네 줄을 한 번에 보냄
        "insert into analysis.item_data_status (item_id, data_kind, status, computed_at) values (%s,%s,%s, now())"
        " on conflict (item_id, data_kind) do update set status = excluded.status, computed_at = now()",
        [
            (item_id, kind, "extracted" if ok else "missing")
            for kind, ok in [
                ("item", True),
                ("status_report", has_sr),
                ("deliveries", bool(events)),
                ("building", bool(bldg)),
            ]  # fmt: skip
        ],
    )
    return True


def load_sales(conn: psycopg.Connection, today: date) -> list[Sale]:
    """최근 12개월 매각 사례 (면적은 우리 물건 표에서 이어 붙임).

    유찰 횟수는 법원 숫자가 아니라 최저가로 센 값(price_round, 0077) — 감정가부터 다시 시작한 물건의
    「13회 유찰 · 80%」 낙찰이 13회 칸에 섞이지 않게(11/24).

    입찰가를 잘못 쓴 것으로 보이는 낙찰(감정가 3배 이상 + 0 하나를 빼도 최저가를 넘음,
    11/17 의정부 2026타경70099 702%)은 특수 사건처럼 비교 사례에서 뺌.
    """
    rows = conn.execute(
        """select s.sale_date, s.sido, i.sigungu, s.usage_name, coalesce(s.building_area_m2, i.building_area_m2),
                  coalesce(s.price_round, s.failed_count), s.sale_rate, s.is_share or s.is_special_case
                  or coalesce(s.sale_rate >= 300 and s.winning_bid_krw >= s.min_price_krw * 10, false), s.address, s.court_code,
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


def load_rule_rows(conn: psycopg.Connection, keys: tuple[str, ...]) -> tuple[RuleRows, dict[tuple[str, str], str]]:
    """기준표 줄 전부(시행일 · 값)와 줄마다 고친 시각 — 물건마다 잔금일로 고름(11/25)."""
    rows: RuleRows = {k: [] for k in keys}
    stamp: dict[tuple[str, str], str] = {}
    for k, vf, v, ch in conn.execute(
        # changed_at 은 0082 — 이주 전에도 돌게 to_jsonb 로 읽음
        "select rule_key, valid_from, value, to_jsonb(t) ->> 'changed_at' from ref.rule_tables t where rule_key = any(%s)",
        (list(keys),),
    ).fetchall():
        rows[k].append((vf, v))
        stamp[(k, vf.isoformat())] = ch or ""
    return rows, stamp


RULE_STAMP: dict[tuple[str, str], str] = {}


def rules_key(p: dict[str, Any]) -> str:
    """고른 줄(시행일 · 고친 시각) + 잔금 기간에 바뀌는 날 — 이게 달라지면 다시 분석."""
    used = ",".join(f"{k}:{vf}:{RULE_STAMP.get((k, vf), '')}" for k, vf in sorted(p["used"].items()))
    after = p["after"]["from"].isoformat() if p.get("after") else ""
    return f"{used}|{after}"


def _diff_line(keys: list[str], since: date, before: dict[str, int], after: dict[str, int], *, applied: bool) -> str | None:
    """집 수(없음 · 1채 · 2채) 중 금액이 1만 원 넘게 달라지는 첫 경우로 한 줄 — 어느 경우도 안 달라지면 알리지 않음."""
    for h, who in (("0", ""), ("1", "1주택이면 "), ("2", "2주택 이상이면 ")):
        if h in before and h in after:
            line = change_line(keys, since, before[h], after[h], applied=applied)
            if line:
                return line.replace(" · ", f" · {who}", 1) if who else line
    return None


def _cash_plan(
    item: dict[str, Any], market: dict[str, Any] | None, today_tables: dict[str, Any] | None,
    bldg: dict[str, Any] | None, rows: RuleRows | None, today: date,
) -> tuple[dict[str, int] | None, dict[str, Any] | None, str | None]:
    """필요한 현금을 잔금일 기준표로. 잔금 기간에 바뀌는 줄이 있으면 두 번 셈해 금액이 다를 때만 알림(11/25)."""
    if not rows:
        return _cash_need(item, market, today_tables, bldg), None, None
    p = rule_plan(rows, CASH_TABLE_KEYS, item.get("sale_date"), today)
    cash = _cash_need(item, market, p["tables"], bldg)
    note = None
    if cash and p["after"]:
        alt = _cash_need(item, market, p["after"]["tables"], bldg) or {}
        line = _diff_line(p["after"]["keys"], p["after"]["from"], cash, alt, applied=False)
        if line:
            note = {"kind": "inside", "from": p["after"]["from"].isoformat(), "keys": p["after"]["keys"],
                    "line": line, "cash_after": alt}  # fmt: skip
    elif cash and p["applied"]:
        now = _cash_need(item, market, today_tables, bldg) or {}
        line = _diff_line(p["applied"]["keys"], p["applied"]["from"], now, cash, applied=True)
        if line:
            note = {"kind": "applied", "from": p["applied"]["from"].isoformat(), "keys": p["applied"]["keys"],
                    "line": line, "cash_today": now}  # fmt: skip
    return cash, note, rules_key(p)


def _cash_need(
    item: dict[str, Any], market: dict[str, Any] | None, tables: dict[str, Any] | None,
    bldg: dict[str, Any] | None = None,
) -> dict[str, int] | None:
    if not tables or not item.get("min_price_krw"):
        return None
    try:
        return cash_at_min(
            min_price_krw=item["min_price_krw"], appraisal_krw=item.get("appraisal_krw"),
            market_krw=(market or {}).get("price_krw"),
            area_m2=float(item["building_area_m2"]) if item.get("building_area_m2") else None,
            sido=item.get("sido"), address=item.get("address"), tables=tables,
            usage=usage_for_kind(item.get("usage_name"), item.get("building_desc"), (bldg or {}).get("unit_use"), (bldg or {}).get("main_use")),  # fmt: skip
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


def rules_stale(conn: psycopg.Connection, rows: RuleRows, today: date, skip: set[str]) -> list[str]:
    """진행 물건 중 지금 고를 기준표가 분석 때 쓴 것과 다른 물건. 끝난 사건은 그때 값 그대로(굳힘)."""
    out = []
    for item_id, sale_date, used in conn.execute(
        """select i.item_id, i.sale_date, a.result ->> 'rules_used' from core.items i
           join lateral (select result from analysis.item_analysis x where x.item_id = i.item_id
                         order by version desc limit 1) a on true
           where i.sale_date >= %s""",
        (today,),
    ).fetchall():
        if item_id in skip or not item_id:
            continue
        if used != rules_key(rule_plan(rows, CASH_TABLE_KEYS, sale_date, today)):
            out.append(item_id)
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
        cash_rows, stamp = load_rule_rows(conn, CASH_TABLE_KEYS)
        RULE_STAMP.clear()
        RULE_STAMP.update(stamp)
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
            # 기준표가 바뀌었거나 잔금 기간에 시행일이 새로 끼게 된 물건만(11/25 — 전체 다시 돌리지 않음)
            ids += rules_stale(conn, cash_rows, today, set(ids))
        else:
            ids = [r[0] for r in conn.execute(
                "select item_id from core.items where sale_date >= %s", (today - timedelta(days=7),)).fetchall()]  # fmt: skip
        conn.commit()
        zones = None
        for k in range(0, len(ids), CHUNK):
            part = ids[k : k + CHUNK]
            pre = None
            if len(part) > 1:  # 한 건(--item)은 예전 길 그대로
                try:
                    zones = zones if zones is not None else load_zones(conn)
                    pre = preload(conn, part, today, zones)
                except (
                    psycopg.Error
                ) as e:  # 묶어 받기가 안 되면 물건마다 받는 예전 길로 — 분석은 멈추지 않음
                    conn.rollback()
                    print(f"묶어 받기 실패 → 물건마다 받음: {type(e).__name__} {str(e)[:120]}")
            for n, item_id in enumerate(part):
                if analyze_item(
                    conn, item_id, sales, today, commercial_table, cash_tables, land_table, pre, cash_rows
                ):
                    job.count += 1
                if pre is None or n % COMMIT_EVERY == COMMIT_EVERY - 1:
                    conn.commit()
            conn.commit()
        if (
            not a.item
        ):  # 추천 점수를 미리 매겨 둠 — 홈은 읽기만(11/14). 여기서 탈이 나도 분석은 끝난 것
            try:
                from aucs_workers.jobs.pick_scores import refresh

                print(f"추천 점수 {refresh(conn, today):,}줄")
            except Exception as e:  # noqa: BLE001
                conn.rollback()
                print(f"추천 점수 매기기 실패(홈은 그때 셈으로): {type(e).__name__} {str(e)[:160]}")
    print(f"분석 {job.count:,}건 (대상 {len(ids):,})")


if __name__ == "__main__":
    main()
