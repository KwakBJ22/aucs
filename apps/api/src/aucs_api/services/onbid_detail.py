"""공매 상세(설계서 4절 「다섯 질문 공매판」). 틀은 경매와 같고 재료만 다름:
회차는 온비드 값 그대로, 낙찰 예상은 최저가 대비 × 응찰자 수, 공매엔 없는 자료는 숨기지 않고 보여 줌."""

import re
from datetime import date, datetime, timedelta
from typing import Any

from aucs_rules.building import lot_key, parse_jibun, summarize
from aucs_rules.fmt import won
from aucs_rules.price import Trade, market_price, trade_region

from aucs_api.cache import memo
from aucs_api.db import batch, connect
from aucs_api.services.item_buy import building_lines
from aucs_api.services.item_links import same_house
from aucs_api.services.onbid import KIND_KO, KST, onbid_card

# 고정 문구(설계서 7절) — 법률이 걸린 문구는 검토 요청서에 올림
MOVE_OUT = "명도는 소송으로 해야 해요 · 보통 6개월~1년 걸려요"
TRUST = "신탁공매예요 · 최우선변제가 경매와 달라 전문가 확인이 필요해요"
TAX_FIRST = (
    "세금이 먼저 배분돼요 · 대항력 있는 임차인이 있으면 보증금보다 세금이 먼저 나갈 수 있어요"
)
MISSING = ["현황조사서", "매각물건명세서", "문건·송달 내역"]
MIN_N = 20  # 이보다 적으면 숫자를 내지 않음
HOUSING = "아파트|다세대|연립|오피스텔|빌라|주택"

_ITEM_SQL = """
select o.*, n.notice_date, n.name as notice_name, n.org_name
from core.onbid_items o left join core.onbid_notices n using (notice_no)
where o.item_id = %s and o.display_policy = 'public'
"""
_ROUNDS_SQL = """
select cond_no, bid_start, bid_end, open_at, min_price_krw, status_name
from core.onbid_rounds where item_id = %s order by bid_end nulls last
"""
_PAST_SQL = """
select opened_at, min_price_krw, win_krw, result, bidders, rate_min
from core.onbid_results where mng_no = %s order by opened_at
"""


def trade_type(usage: str | None, title: str | None) -> str | None:
    t = f"{usage or ''} {title or ''}"
    if "오피스텔" in t:
        return "officetel"
    if "아파트" in t:
        return "apt"
    if re.search("다세대|연립|빌라", t):
        return "rowhouse"
    return None


@memo(ttl=3600)
def expected_rates(housing: bool) -> list[dict[str, Any]]:
    """서울·경기 공매 낙찰의 최저가 대비 낙찰가율 — 응찰자 수별 가운데값과 가운데 절반. 표본 MIN_N 미만은 숫자 없음."""
    sql = """
    with t as (
      select rate_min, case when coalesce(bidders, 1) <= 1 then 1 when bidders = 2 then 2
                            when bidders <= 4 then 3 else 5 end as b
      from core.onbid_results
      where result = '낙찰' and rate_min is not null and sido in ('서울특별시', '경기도')
        and (concat_ws(' ', usage_l, usage_m, usage_s, title) ~ %(h)s) = %(housing)s)
    select b, count(*) as n,
           percentile_cont(0.25) within group (order by rate_min) as p25,
           percentile_cont(0.5) within group (order by rate_min) as p50,
           percentile_cont(0.75) within group (order by rate_min) as p75,
           min(x.total) as total
    from t, (select count(*) as total from t) x group by b order by b"""
    with connect() as c:
        rows = c.execute(sql, {"h": HOUSING, "housing": housing}).fetchall()
    label = {1: "혼자", 2: "2명", 3: "3~4명", 5: "5명 이상"}
    return [
        {
            "bucket": label[r["b"]],
            "n": r["n"],
            "share": round(r["n"] * 100 / r["total"]) if r["total"] else None,
            "p25": round(float(r["p25"]), 1) if r["n"] >= MIN_N else None,
            "p50": round(float(r["p50"]), 1) if r["n"] >= MIN_N else None,
            "p75": round(float(r["p75"]), 1) if r["n"] >= MIN_N else None,
        }
        for r in rows
    ]


def rounds_view(
    rounds: list[dict[str, Any]],
    past: list[dict[str, Any]],
    current_end: datetime | None,
    app: int | None,
) -> list[dict[str, Any]]:
    """지난(입찰 결과) + 이번 + 다음 회차. 온비드가 공고한 회차만, 계산으로 늘리지 않음. (순수 함수)"""
    out: list[dict[str, Any]] = []
    for p in past[-2:]:
        out.append({"label": "지난", "bid_end": None, "open_at": p["opened_at"].isoformat(),
                    "min_price_krw": p["min_price_krw"], "result": p["result"],
                    "rate": round(p["min_price_krw"] * 100 / app) if app and p["min_price_krw"] else None})  # fmt: skip
    for x in rounds:
        if current_end and x["bid_end"] and x["bid_end"] < current_end:
            continue
        label = "이번" if x["bid_end"] == current_end else "다음"
        out.append({
            "label": label,
            "bid_start": x["bid_start"].isoformat() if x["bid_start"] else None,
            "bid_end": x["bid_end"].isoformat() if x["bid_end"] else None,
            "open_at": x["open_at"].isoformat() if x["open_at"] else None,
            "min_price_krw": x["min_price_krw"],
            "result": None,
            "rate": round(x["min_price_krw"] * 100 / app) if app and x["min_price_krw"] else None,
        })  # fmt: skip
    return out[:5]


def market_of(
    trades: list[dict[str, Any]], lot: str | None, area: float | None, today: date
) -> dict[str, Any] | None:
    """같은 지번·같은 면적(±3㎡) 최근 24개월 매매로 시세(경매와 같은 규칙). (순수 함수)"""
    if not trades or not lot or not area:
        return None
    ts = [
        Trade(
            r["deal_date"],
            int(r["price_krw"]),
            float(r["area_m2"]),
            r["floor"],
            lot,
            r["build_year"],
        )
        for r in trades
    ]
    res = market_price(ts, as_of=today, complex_name=lot, area_m2=float(area))
    if res.value is None:
        return None
    prices = sorted(e["price_krw"] for e in res.evidence)
    n = len(prices)
    return {
        **res.value,
        "lo_krw": prices[n // 4] if n >= 4 else prices[0],
        "hi_krw": prices[(3 * n) // 4] if n >= 4 else prices[-1],
        "recent": sorted(res.evidence, key=lambda e: e["date"], reverse=True)[:3],
    }


def building_summary(c: Any, r: dict[str, Any], today: date) -> dict[str, Any] | None:
    """건축물대장(collectors/buildings 가 공매 물건도 받음) → 요약(층·승강기·연식 등)."""
    p = parse_jibun(r["lot_no"])
    if not p or not r["region_code"]:
        return None
    rows = c.execute(
        "select kind, data from core.building_register where region_code = %s and lot_no = %s order by kind, seq",
        (r["region_code"], lot_key(*p)),
    ).fetchall()
    titles = [x["data"] for x in rows if x["kind"] == "title"]
    floors = [x["data"] for x in rows if x["kind"] == "floor"]
    addr = r["address"] or r["title"]
    return summarize(titles, floors, addr, f"{r['usage_name'] or ''} {r['title'] or ''}", today)


def building_of(c: Any, r: dict[str, Any], today: date) -> dict[str, Any] | None:
    """「무엇을 사나」 건물 줄."""
    return building_lines(building_summary(c, r, today))


def checklist(kind: str) -> list[dict[str, Any]]:
    """공매 체크리스트 6개(설계서 4절). 처음엔 건축물대장만 끝난 것으로 보지 않음(공매 물건은 아직 대장을 안 붙임)."""
    return [
        {"key": "registry", "label": "등기부", "state": "미확인", "what": "인터넷등기소 PDF를 올리면 권리를 정리해 드려요"},
        {"key": "tenant", "label": "점유자·임차인", "state": "공매엔 없어요", "what": "주민센터 전입세대 열람 (본인이 직접)"},
        {"key": "rights", "label": "떠안는 권리", "state": "미확인", "what": "등기부 사다리 + 공고 특이 조건"},
        {"key": "dues", "label": "관리비 밀린 돈", "state": "미확인", "what": "관리사무소 전화 (현장 갈 때)"},
        {"key": "move_out", "label": "명도 계획", "state": "전문가 확인 필요",
         "what": "인도명령이 없어 소송으로 · 현장에서 누가 사는지 먼저"},
        {"key": "trust", "label": "신탁 원부", "state": "전문가 확인 필요" if kind == "trust" else "해당 없음",
         "what": "신탁공매는 최우선변제가 달라요 · 신탁원부와 우선수익권 순위를 보세요"},
    ]  # fmt: skip


@memo()
def detail(item_id: str, today: date) -> dict[str, Any] | None:
    with connect() as c:
        q_item, q_rounds = batch(c, [(_ITEM_SQL, (item_id,)), (_ROUNDS_SQL, (item_id,))])
        r = q_item.fetchone()
        rounds = q_rounds.fetchall()
        if not r:
            return None
        past = c.execute(_PAST_SQL, (r["mng_no"],)).fetchall()
        bldg = building_of(c, r, today)
        kind = trade_type(r["usage_name"], r["title"])
        trades = []
        if kind and r["region_code"] and r["lot_no"]:
            trades = c.execute(
                """select deal_date, price_krw, area_m2, floor, build_year from core.trades
                   where region_code = %s and prop_type = %s and deal_kind = 'sale' and lot_no = %s
                     and deal_date >= %s and price_krw > 0""",
                (trade_region(r["region_code"]), kind, r["lot_no"], today - timedelta(days=730)),
            ).fetchall()
    base = onbid_card({**r, "next_round": None}, today)
    app, mn = r["appraisal_krw"], r["min_price_krw"]
    area = r["building_m2"] or r["land_m2"]
    mkt = market_of(trades, r["lot_no"], float(area) if area else None, today)
    housing = bool(re.search(HOUSING, f"{r['usage_name'] or ''} {r['title'] or ''}"))
    exp = expected_rates(housing)
    for e in exp:
        e["price_krw"] = int(mn * e["p50"] / 100) if mn and e["p50"] else None
    rv = rounds_view(rounds, past, r["bid_end"], app)
    nxt = next((x for x in rv if x["label"] == "다음"), None)
    warnings = [MOVE_OUT]
    if r["kind"] == "trust":
        warnings.insert(0, TRUST)
    elif r["kind"] == "seized":
        warnings.append(TAX_FIRST)
    verdict = (
        "신탁공매예요 · 판정은 전문가 확인 뒤에 해요"
        if r["kind"] == "trust"
        else "공개 자료가 적은 공매예요 · 현장과 등기부부터 보세요"
    )
    ck = checklist(r["kind"])
    todo = [x for x in ck if x["state"] not in ("확인 완료", "해당 없음")]
    return {
        **base,
        "same_house": same_house(item_id),
        "title": r["title"],
        "address": r["address"],
        "kind_name": KIND_KO.get(r["kind"], r["kind_name"]),
        "bid_start": r["bid_start"].isoformat() if r["bid_start"] else None,
        "open_at": r["open_at"].isoformat() if r["open_at"] else None,
        "status_name": r["status_name"],
        "gone": r["status_code"] == "gone",
        "notice": {
            "no": r["notice_no"],
            "date": r["notice_date"].isoformat() if r["notice_date"] else None,
            "name": r["notice_name"],
            "org": r["org_name"],
        },  # fmt: skip
        "verdict": verdict,
        "fatal": "온비드 목록에서 빠졌어요 · 취소일 수 있어요"
        if r["status_code"] == "gone"
        else warnings[0],
        "warnings": warnings,
        "missing_docs": MISSING,
        "building": bldg,
        "rounds": rv,
        "wait_line": (
            f"기다리면 {won((mn or 0) - nxt['min_price_krw'])} 원 싸지지만, 이번 주에 누가 먼저 사면 끝이에요"
            if nxt and mn and nxt["min_price_krw"] and nxt["min_price_krw"] < mn
            else None
        ),
        "market": mkt,
        "market_rate": round(mn * 100 / mkt["price_krw"]) if mkt and mn else None,
        "appraisal_vs_market": round(app * 100 / mkt["price_krw"]) if mkt and app else None,
        "expected": exp,
        "expected_basis": f"서울·경기 공매 {'주택' if housing else '주택 아닌 물건'} 낙찰 {sum(e['n'] for e in exp):,}건",
        "checklist": ck,
        "check_left": len(todo),
        "deposit_krw": mn // 10 if mn else None,
        "computed_at": datetime.now(KST).isoformat(timespec="minutes"),
    }
