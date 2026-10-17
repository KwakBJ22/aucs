"""물건 상세(ITEM-01 다섯 질문). DB에서 모으는 부분과 화면 묶음을 만드는 부분(순수 함수)을 나눴습니다."""

from datetime import date
from typing import Any

from aucs_rules.sale_rate import next_round_min_price

from aucs_api.db import connect
from aucs_api.services.items import card

_ITEM_SQL = """
select i.*, c.court_code, c.case_no, c.claim_deadline, c.dept_name,
       st_y(i.geom::geometry) as lat, st_x(i.geom::geometry) as lon,
       a.result -> 'top' as top, a.result -> 'signals' as signals, a.result -> 'sale_rate' as sale_rate,
       a.computed_at,
       coalesce((select json_object_agg(d.data_kind, d.status) from analysis.item_data_status d where d.item_id = i.item_id), '{}') as data_status
from core.items i
join core.cases c using (case_id)
left join lateral (select result, computed_at from analysis.item_analysis x where x.item_id = i.item_id order by version desc limit 1) a on true
where i.item_id = %s and i.display_policy = 'public'
"""

RESULT_KO = {
    "scheduled": "예정",
    "sold": "매각",
    "failed": "유찰",
    "changed": "변경",
    "withdrawn": "취하",
    "unknown": "모름",
}
TAGS = [
    ("status_report", "현황조사"),
    ("spec_sheet", "명세서"),
    ("deliveries", "문건"),
    ("registry", "등기부"),
    ("building", "건축물대장"),
]


def won(v: int | None) -> str:
    if not v:
        return "-"
    eok, man = divmod(v // 10_000, 10_000)
    if eok and man:
        return f"{eok}억 {man:,}만"
    return f"{eok}억" if eok else f"{man:,}만"


def verdict(signals: list[dict[str, Any]]) -> str:
    """맨 위 한 줄 판정. 치명 > 주의 > 모름 > 문제 없음."""
    fatal = [s for s in signals if s.get("level") == "fatal"]
    if fatal:
        return f"{fatal[0]['title']} — 초보자는 피하는 게 좋아요"
    warn = [s for s in signals if s.get("level") in ("high", "mid") and s.get("status") != "모름"]
    unknown = [s for s in signals if s.get("status") == "모름"]
    if warn:
        return f"{warn[0]['title']}" + (f" · 확인할 것 {len(unknown)}가지" if unknown else "")
    if unknown:
        return f"큰 문제 신호는 없어요. 확인할 것 {len(unknown)}가지만 보면 돼요"
    return "큰 문제 신호는 없어요"


def build_detail(
    r: dict[str, Any],
    rounds: list[dict[str, Any]],
    events: list[dict[str, Any]],
    tenants: list[dict[str, Any]],
    reduction: dict[str, Any] | None,
    today: date,
) -> dict[str, Any]:
    c = card(r, today)
    signals = r["signals"] or []
    rate = r["sale_rate"]
    app, mn = r["appraisal_krw"], r["min_price_krw"]
    nxt = next_round_min_price(mn, reduction["pct"] if reduction else None) if mn else None
    ds = r["data_status"] or {}
    unknown = [s for s in signals if s.get("status") == "모름"]
    warn = [
        s
        for s in signals
        if s.get("level") in ("fatal", "high", "mid") and s.get("status") != "모름"
    ]

    def q(key: str, title: str, answer: str, tone: str, body: dict[str, Any]) -> dict[str, Any]:
        return {"key": key, "title": title, "answer": answer, "tone": tone, "body": body}

    area = f"{round(c['area_m2'])}㎡ · " if c["area_m2"] else ""
    rate_ans = (
        f"비슷한 물건은 감정가의 {round(rate['p25'])}~{round(rate['p75'])}%에 낙찰됐어요"
        if rate else "비교할 낙찰 사례가 부족해요"
    )  # fmt: skip
    hold_ans = (
        warn[0]["title"] if warn
        else f"임차인 {len(tenants)}명 · 등기부는 아직 안 봤어요" if tenants
        else "임차인 자료가 없어요 · 등기부는 아직 안 봤어요"
    )  # fmt: skip
    questions = [
        q("buy", "무엇을 사나", f"{area}{r['usage_name'] or ''} {r['building_desc'] or ''}".strip(), "gray",
          {"address": r["address"], "area_m2": c["area_m2"], "usage": r["usage_name"], "building": r["building_desc"],
           "is_share": r["is_share"], "note": r["note_masked"]}),
        q("hold", "무엇을 떠안나", hold_ans, "red" if any(s.get("level") == "fatal" for s in warn) else "orange" if warn else "gray",
          {"tenants": tenants, "signals": signals}),
        q("worth", "얼마짜리인가", rate_ans, "gray" if not rate else "blue",
          {"appraisal_krw": app, "rate": rate,
           "range_krw": [int(app * rate["p25"] / 100), int(app * rate["p75"] / 100)] if rate and app else None}),
        q("cost", "얼마가 드나", f"입찰보증금 {won(c['deposit_krw'])}원부터", "gray",
          {"deposit_krw": c["deposit_krw"], "min_price_krw": mn}),
        q("check", "무엇을 확인하나", f"확인할 것 {len(unknown)}가지" if unknown else "자료는 다 모였어요",
          "gray" if unknown else "green",
          {"unknown": unknown, "events": events,
           "claim_deadline": r["claim_deadline"].isoformat() if r["claim_deadline"] else None}),
    ]  # fmt: skip
    return {
        **c,
        "verdict": verdict(signals),
        "fatal": next((s["title"] for s in signals if s.get("level") == "fatal"), None),
        "address": r["address"],
        "sale_place": r["sale_place"],
        "dept_name": r["dept_name"],
        "next_round": {
            "min_price_krw": nxt.value if nxt else None,
            "reduction_pct": reduction["pct"] if reduction else None,
            "verified": bool(reduction and reduction.get("verified")),
        },
        "rounds": [
            {
                "sale_date": x["sale_date"].isoformat(),
                "min_price_krw": x["min_price_krw"],
                "result": RESULT_KO.get(x["result"], x["result"]),
            }
            for x in rounds
        ],  # fmt: skip
        "tags": [
            {"label": label, "ok": ds.get(k) in ("extracted", "verified", "fetched")}
            for k, label in TAGS
        ],
        "questions": questions,
        "computed_at": r["computed_at"].isoformat() if r["computed_at"] else None,
    }


def detail(item_id: str, today: date) -> dict[str, Any] | None:
    with connect() as c:
        r = c.execute(_ITEM_SQL, (item_id,)).fetchone()
        if not r:
            return None
        rounds = c.execute(
            "select sale_date, min_price_krw, result from core.rounds where item_id = %s order by sale_date",
            (item_id,),
        ).fetchall()
        events = c.execute(
            """select event_date::text as date, category, importance, text_masked as text, after_deadline
               from core.case_events where case_id = %s and importance in ('high', 'mid')
               order by event_date desc nulls last limit 12""",
            (r["case_id"],),
        ).fetchall()
        tenants = c.execute(
            """select name_masked as name, occupied_part as part, move_in_date::text as move_in,
                      fixed_date::text as fixed, claim_date::text as claim, deposit_krw, monthly_rent_krw
               from core.tenants where case_id = %s order by move_in_date nulls last""",
            (r["case_id"],),
        ).fetchall()
        red = c.execute(
            "select value -> %s as v from ref.rule_tables where rule_key = 'court_reduction_pct' "
            "and valid_from <= %s order by valid_from desc limit 1",
            (r["court_code"], today),
        ).fetchone()
    return build_detail(r, rounds, events, tenants, red["v"] if red else None, today)
