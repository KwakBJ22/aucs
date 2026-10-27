"""물건 상세(ITEM-01 다섯 질문). DB에서 모으는 부분과 화면 묶음을 만드는 부분(순수 함수)을 나눴습니다."""

from datetime import date, timedelta
from typing import Any

from aucs_rules.risk import FAILURE_TYPES
from aucs_rules.sale_rate import next_round_min_price, restarted
from aucs_rules.schedule import after_sale

from aucs_api.cache import memo
from aucs_api.db import batch, connect
from aucs_api.services.checklist import DONE, build_checklist, build_flow
from aucs_api.services.docs import spec_sheet, spec_text
from aucs_api.services.items import COURT_NAME, card

_ITEM_SQL = """
select i.*, c.court_code, c.case_no, c.claim_deadline, c.dept_name,
       st_y(i.geom::geometry) as lat, st_x(i.geom::geometry) as lon,
       a.result -> 'top' as top, a.result -> 'signals' as signals, a.result -> 'sale_rate' as sale_rate,
       a.result -> 'court_cell' as court_cell, a.result -> 'local_peers' as local_peers,
       a.result -> 'new_item' as new_item, a.result -> 'market' as market, a.result -> 'redev' as redev,
       a.result -> 'building' as building, a.computed_at,
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


def _one(r: dict[str, Any] | None) -> dict[str, Any]:
    """꼭 있어야 하는 한 줄(기준표 등). 없으면 설정 오류라 바로 알림."""
    if r is None:
        raise LookupError("기준표가 비어 있어요")
    return r


def failure_table(signals: list[dict[str, Any]]) -> list[dict[str, str]]:
    """PC 전문가 보기: 실패 11유형 전체와 이 물건 상태(걸림·확인 필요·신호 없음). 신호 없음 ≠ 안전."""
    out = []
    for code, title in FAILURE_TYPES.items():
        mine = [s for s in signals if s.get("ftype") == code]
        hit = [
            s
            for s in mine
            if s.get("level") in ("fatal", "high", "mid")
            and s.get("status") not in ("모름", "확인 필요")
        ]
        if hit:
            state, why = "걸림", hit[0]["title"]
        elif mine:
            state, why = "확인 필요", mine[0]["title"]
        else:
            state, why = "신호 없음", ""
        out.append({"code": code, "title": title, "state": state, "why": why})
    return out


def won(v: int | None) -> str:
    if not v:
        return "-"
    eok, man = divmod(v // 10_000, 10_000)
    if eok and man:
        return f"{eok}억 {man:,}만"
    return f"{eok}억" if eok else f"{man:,}만"


PENDING = "오늘 오후 분석이 끝나면 보여요"
GONE_LINE = "법원 목록에서 빠졌어요 · 기일 변경이나 취하일 수 있어요 · 법원에서 확인하세요"


def verdict(signals: list[dict[str, Any]], n_check: int | None = None) -> str:
    """맨 위 한 줄 판정. 치명 > 주의 > 모름 > 문제 없음.

    n_check: 「무엇을 확인하나」의 남은 확인 수 — 주면 그 수를 씀(두 곳 숫자가 어긋나지 않게, 10/19 점검)."""
    fatal = [s for s in signals if s.get("level") == "fatal"]
    if fatal:
        return f"{fatal[0]['title']} — 초보자는 피하는 게 좋아요"
    warn = [s for s in signals if s.get("level") in ("high", "mid") and s.get("status") != "모름"]
    n = len([s for s in signals if s.get("status") == "모름"]) if n_check is None else n_check
    if warn:
        return f"{warn[0]['title']}" + (f" · 확인할 것 {n}가지" if n else "")
    if n:
        return f"큰 문제 신호는 없어요. 확인할 것 {n}가지만 보면 돼요"
    return "큰 문제 신호는 없어요"


# 감정가가 같은 단지 시세의 이 범위 밖이면 시세 비교를 빼고 이유를 한 줄로 (10/19 대표님)
APPRAISAL_SANE = (0.55, 1.6)


# 명세서에 적히면 감정가가 낮게 잡히는 사정
SPEC_WORDS = [
    "위반건축",
    "대지권",
    "토지별도등기",
    "별도등기",
    "유치권",
    "법정지상권",
    "제시외",
    "지분",
    "맹지",
]


def appraisal_gap(
    r: dict[str, Any], signals: list[dict[str, Any]], spec_txt: str = ""
) -> tuple[str, str] | None:
    """감정가가 시세와 크게 다를 때 (이유 종류, 안내). 이유는 명세서 비고란·신호로 찾음.

    종류: share(지분) / special(특별조건) / note(비고란 있음) / none(이유 모름)."""
    mkt, app = r.get("market"), r.get("appraisal_krw")
    if not mkt or not app or not mkt.get("price_krw"):
        return None
    ratio = app / mkt["price_krw"]
    if APPRAISAL_SANE[0] <= ratio <= APPRAISAL_SANE[1]:
        return None
    ids = {s.get("rule_id") for s in signals if s.get("status") != "모름"}
    if ratio < 1 and (r.get("is_share") or "risk.share" in ids):
        return (
            "share",
            "지분만 파는 물건이라 감정가도 지분 몫이에요 · 단지 시세와 바로 비교하면 안 돼요",
        )
    if ratio > 1 and "risk.special_condition" in ids:
        return "special", "전세 피해 주택이라 감정가가 실제 거래보다 높게 잡혔을 수 있어요"
    found = next((w for w in SPEC_WORDS if w in spec_txt), None)
    if ratio < 1 and found:
        return (
            "spec",
            f"명세서에 「{found}」 내용이 있어요 · 감정가가 낮게 잡힌 이유일 수 있어요(명세서 원문 보기)",
        )
    deal = f"감정가가 같은 단지 거래({won(mkt['price_krw'])})와 크게 달라요"
    if (r.get("note_masked") or "").strip():
        return "note", f"{deal} · 비고란 조건을 먼저 보세요(「무엇을 사나」)"
    return "none", f"{deal} · 다른 평형 거래일 수도 있어요"


def worth(
    r: dict[str, Any], signals: list[dict[str, Any]], spec_txt: str = ""
) -> tuple[str, list[str], Any]:
    """「얼마짜리인가」 한 줄과 경고 줄. 관할 법원 칸이 기준을 바꾸면 범위를 그만큼 옮깁니다(입찰가 산정 1C~1E)."""
    rate, court, peers = r.get("sale_rate"), r.get("court_cell"), r.get("local_peers")
    notes: list[str] = []
    mkt, app, mn = r.get("market"), r.get("appraisal_krw"), r.get("min_price_krw")
    gap = appraisal_gap(r, signals, spec_txt)
    if gap:
        notes.append(gap[1])
        mkt = None
    # 「처음 나온 물건」은 최저가가 감정가 그대로일 때만 (유찰 수 자료가 빠진 물건이 있음)
    if restarted(r.get("failed_count"), app, mn):
        notes.append(
            f"유찰 {r['failed_count']}회 뒤 매각조건이 바뀌어 감정가부터 다시 시작해요(최저가=감정가)"
        )
    if r.get("new_item") and (not app or not mn or mn >= app):
        if gap:  # 감정가를 그대로 믿기 어려운 신건 → 「비싸게 팔려요」라고 하지 않음
            return (
                "처음 나온 물건이에요 · 감정가가 시세와 크게 달라 아래 안내를 먼저 보세요",
                notes,
                None,
            )
        if mkt and mkt["price_krw"] < app:
            return (
                f"처음 나온 물건이지만 시세({won(mkt['price_krw'])})가 감정가보다 낮아요",
                notes,
                None,
            )
        if restarted(r.get("failed_count"), app, mn):
            return "감정가부터 다시 시작한 물건이라 처음 나온 물건처럼 보면 돼요", notes, None
        return "처음 나온 물건이라 보통 감정가보다 비싸게 팔려요", notes, None
    if not rate:
        return "비교할 낙찰 사례가 부족해요", notes, None
    lo, mid, hi, shift = rate["p25"], rate["p50"], rate["p75"], 0.0
    if court and court.get("use_as_base"):
        shift = court["diff"]
        lo, mid, hi = lo + shift, mid + shift, hi + shift
        notes.append(
            f"이 법원은 같은 조건에서 {abs(round(shift))}%p {'높게' if shift > 0 else '낮게'} 팔려요"
        )
    if peers and peers.get("warn"):
        notes.append(
            f"같은 구 최근 {peers['n']}건은 {round(peers['lo'])}~{round(peers['hi'])}%에 팔렸어요"
        )
    if not gap and any(s.get("rule_id") == "risk.low_appraisal" for s in signals):
        notes.append("감정가가 시세보다 낮아 더 높게 팔릴 수 있어요")
    # 최저가보다 낮게는 낙찰될 수 없음 → 범위 아래쪽을 최저가에 맞춤
    floor = mn / app * 100 if mn and app else None
    below = bool(floor and hi < floor)
    if floor:
        lo, mid, hi = max(lo, floor), max(mid, floor), max(hi, floor)
    ans = f"비슷한 물건은 감정가의 {round(lo)}~{round(hi)}%에 낙찰됐어요"
    if below:
        ans = "비슷한 물건이 이번 최저가보다 싸게 팔려서 최저가 근처에서 낙찰될 것 같아요"
    elif mkt and app:
        a, b = app * lo / mkt["price_krw"], app * hi / mkt["price_krw"]
        ans = f"시세의 {round(a)}~{round(b)}%쯤에 낙찰될 것 같아요"
    return ans, notes, {**rate, "p25": lo, "p50": mid, "p75": hi, "court_shift": shift}


def building_lines(b: dict[str, Any] | None) -> dict[str, Any] | None:
    """건축물대장 요약 → 화면 줄(값만, 같은 설명 되풀이 없이). 못 받았으면 None."""
    if not b:
        return None
    floors = " / ".join(
        x for x in [f"지상 {b['floors_above']}층" if b.get("floors_above") else None,
                    f"지하 {b['floors_below']}층" if b.get("floors_below") else None] if x
    )  # fmt: skip
    built = f"{b['approved'][:4]}년 사용승인 · {b['age_years']}년 됨" if b.get("approved") else None
    extra = " · ".join(
        x for x in [f"{b['households']}세대" if b.get("households") else None,
                    f"승강기 {b['elevators']}대" if b.get("elevators") else None,
                    f"주차 {b['parking']}대" if b.get("parking") else None] if x
    )  # fmt: skip
    unit = None
    if b.get("unit_floor") is not None and b.get("unit_floor_uses"):
        f = b["unit_floor"]
        unit = f"{'지하 ' + str(-f) if f < 0 else f}층 용도: {', '.join(b['unit_floor_uses'])}"
    return {
        "built": built,
        "old": bool(b.get("age_years") and b["age_years"] >= 30),
        "shape": " · ".join(x for x in [b.get("main_use"), b.get("structure"), floors] if x)
        or None,
        "extra": extra or None,
        "unit": unit,
        "villa": b.get("villa"),
        "dong": b.get("dong"),
    }


def build_detail(
    r: dict[str, Any],
    rounds: list[dict[str, Any]],
    events: list[dict[str, Any]],
    tenants: list[dict[str, Any]],
    reduction: dict[str, Any] | None,
    today: date,
    holidays: list[date] | None = None,
    doc_times: dict[str, Any] | None = None,
    spec: dict[str, Any] | None = None,
) -> dict[str, Any]:
    c = card(r, today)
    signals = r["signals"] or []
    stxt = spec_text(spec)
    rate_ans, rate_notes, rate = worth(r, signals, stxt)
    analyzed = r.get("computed_at") is not None
    if not analyzed:
        rate_ans = PENDING
    app, mn = r["appraisal_krw"], r["min_price_krw"]
    nxt = next_round_min_price(mn, reduction["pct"] if reduction else None) if mn else None
    ds = dict(r["data_status"] or {})
    if spec:  # 물건상세에 명세서 내용이 들어와 있으면 받은 것으로
        ds["spec_sheet"] = "extracted"
    warn = [
        s
        for s in signals
        if s.get("level") in ("fatal", "high", "mid") and s.get("status") != "모름"
    ]

    def q(key: str, title: str, answer: str, tone: str, body: dict[str, Any]) -> dict[str, Any]:
        return {"key": key, "title": title, "answer": answer, "tone": tone, "body": body}

    area = f"{round(c['area_m2'])}㎡ · " if c["area_m2"] else ""
    flags = ["farmland"] if any(s.get("rule_id") == "risk.farmland" for s in signals) else []
    sched = after_sale(r["sale_date"] or today, holidays or [], flags=flags).value
    types = sorted({s["ftype"] for s in warn if s.get("ftype")})
    checklist = build_checklist(ds, doc_times or {}, signals)
    gap = appraisal_gap(r, signals, stxt)
    if gap and gap[0] in ("note", "none"):  # 지분·특별조건은 이미 위험 신호로 올라가 있음
        checklist = sorted(
            [*checklist, {"key": "appraisal_gap", "label": "감정가·시세 차이", "what": gap[1],
                          "state": "미확인", "hint": None, "evidence": None}],
            key=lambda x: {"자료 충돌": 0, "전문가 확인 필요": 1, "미확인": 2}.get(x["state"], 3),
        )  # fmt: skip
    todo = [x for x in checklist if x["state"] != DONE]
    check_ans = f"확인할 것 {len(todo)}가지 · {todo[0]['label']}부터" if todo else "다 확인했어요"
    check_tone = (
        "orange" if any(x["state"] in ("자료 충돌", "전문가 확인 필요") for x in todo) else "gray"
    )
    flow = build_flow(
        events=events, claim_deadline=r["claim_deadline"], rounds=rounds, sale_date=r["sale_date"],
        schedule_rows=sched["rows"], today=today, failed_count=r.get("failed_count"),
    )  # fmt: skip
    hold_ans = (
        warn[0]["title"] if warn
        else f"임차인 {len(tenants)}명 · 등기부는 아직 안 봤어요" if tenants
        else "현황조사서에 임차인이 없어요 · 등기부는 아직 안 봤어요" if ds.get("status_report") in ("extracted", "verified")
        else "임차인 자료가 없어요 · 등기부는 아직 안 봤어요"
    )  # fmt: skip
    questions = [
        q("buy", "무엇을 사나", f"{area}{r['usage_name'] or ''}".strip(" ·"), "gray",
          {"address": r["address"], "area_m2": c["area_m2"], "usage": r["usage_name"],
           "is_share": r["is_share"], "note": r["note_masked"], "redev": r.get("redev"),
           "building": building_lines(r.get("building"))}),
        q("hold", "무엇을 떠안나", hold_ans, "red" if any(s.get("level") == "fatal" for s in warn) else "orange" if warn else "gray",
          {"tenants": tenants, "signals": signals}),
        q("worth", "얼마짜리인가", rate_ans, "gray" if not rate else "blue",
          {"appraisal_krw": app, "rate": rate, "notes": rate_notes, "market": r.get("market"),
           "range_krw": [int(app * rate["p25"] / 100), int(app * rate["p75"] / 100)] if rate and app else None}),
        q("cost", "얼마가 드나", f"입찰보증금 {won(c['deposit_krw'])}원부터", "gray",
          {"deposit_krw": c["deposit_krw"], "min_price_krw": mn, "schedule_line": sched["summary"]["line"],
           "deadlines": [x for x in sched["rows"] if x["deadline"]]}),
        q("check", "무엇을 확인하나", check_ans, check_tone,
          {"checklist": checklist, "flow": flow, "events": events,
           "claim_deadline": r["claim_deadline"].isoformat() if r["claim_deadline"] else None}),
    ]  # fmt: skip
    return {
        **c,
        "verdict": verdict(signals, len(todo)) if analyzed else PENDING,
        "analyzed": analyzed,
        "fatal": GONE_LINE
        if r.get("status_code") == "gone"
        else next((s["title"] for s in signals if s.get("level") == "fatal"), None),
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
        "failure_types": [{"code": t, "title": FAILURE_TYPES[t]} for t in types],
        "failure_table": failure_table(signals),
        "schedule": sched,
        "computed_at": r["computed_at"].isoformat() if r["computed_at"] else None,
    }


_CASE = "(select case_id from core.items where item_id = %s)"

_PEERS_SQL = """
with it as (
  select i.item_id, c.case_no, i.lot_no, coalesce(i.gu, i.sigungu) as q,
         regexp_replace(r.eupmyeondong, '^.* ', '') as dong
  from core.items i join core.cases c using (case_id)
  join ref.regions r on r.region_code = i.region_code and r.level = 'dong'
  where i.item_id = %s and coalesce(i.lot_no, '') ~ '^산?[0-9]+(-[0-9]+)?$'
)
select * from (
select distinct on (s.court_code, s.case_no, s.item_no)
       s.sale_date, s.winning_bid_krw, s.appraisal_krw, s.sale_rate, s.failed_count, s.building_area_m2,
       s.court_code, s.case_no, s.address
from core.sale_results s, it
where s.result = 'sold' and s.case_no <> it.case_no and s.winning_bid_krw > 0
  and s.address ~ ('(^| )' || it.dong || ' ' || it.lot_no || '( |\\[|,|$)') and s.address like '%%' || it.q || '%%'
order by s.court_code, s.case_no, s.item_no, s.sale_date desc
) x order by sale_date desc limit 8
"""


def _unit(address: str | None) -> str | None:
    """「306동 6층」 — 같은 단지 안 어느 집인지(호수는 뺌)."""
    from aucs_rules.building import unit_from_address

    u = unit_from_address(address)
    parts = [
        f"{u['dong']}동" if u["dong"] else None,
        (f"지하 {-u['floor']}층" if u["floor"] < 0 else f"{u['floor']}층") if u["floor"] else None,
    ]
    return " ".join(x for x in parts if x) or None


def c_area(r: dict[str, Any]) -> float | None:
    return float(r["building_area_m2"]) if r.get("building_area_m2") else None


def _median(xs: list[int]) -> int | None:
    if not xs:
        return None
    ys = sorted(xs)
    n = len(ys)
    return ys[n // 2] if n % 2 else (ys[n // 2 - 1] + ys[n // 2]) // 2


def build_complex(
    trades: list[dict[str, Any]], peers: list[dict[str, Any]], area: float | None, today: date
) -> dict[str, Any] | None:
    """같은 단지: 지난 낙찰과 실거래 추이(최근 6개월 vs 그 앞 6개월, 전세·월세 1년). 없으면 None. (순수 함수)"""
    near = [
        t for t in trades if not area or (t["area_m2"] and abs(float(t["area_m2"]) - area) <= 3)
    ]
    d6, d12 = today - timedelta(days=183), today - timedelta(days=366)
    sale = [t for t in near if t["deal_kind"] == "sale" and t["price_krw"]]
    recent = [t["price_krw"] for t in sale if t["deal_date"] >= d6]
    prev = [t["price_krw"] for t in sale if d12 <= t["deal_date"] < d6]
    lease = [
        t for t in near if t["deal_kind"] == "lease" and t["deal_date"] >= d12 and t["deposit_krw"]
    ]
    jeonse = [t["deposit_krw"] for t in lease if not t["monthly_rent_krw"]]
    wolse = [t for t in lease if t["monthly_rent_krw"]]
    rm, pm = _median(recent), _median(prev)
    trend = {
        "recent_krw": rm, "recent_n": len(recent), "prev_krw": pm, "prev_n": len(prev),
        "change_pct": round((rm - pm) * 100 / pm, 1) if rm and pm and len(recent) >= 2 and len(prev) >= 2 else None,
        "jeonse_krw": _median(jeonse), "jeonse_n": len(jeonse),
        "wolse_deposit_krw": _median([t["deposit_krw"] for t in wolse]),
        "wolse_rent_krw": _median([t["monthly_rent_krw"] for t in wolse]), "wolse_n": len(wolse),
        "area_match": bool(area),
    }  # fmt: skip
    quarters: dict[str, list[int]] = {}
    for t in sale:
        quarters.setdefault(
            f"{t['deal_date'].year % 100}.{(t['deal_date'].month - 1) // 3 + 1}분기", []
        ).append(t["price_krw"])
    auctions = [
        {"date": p["sale_date"].isoformat(), "price_krw": p["winning_bid_krw"],
         "rate": round(float(p["sale_rate"])) if p["sale_rate"] is not None else None,
         "area_m2": float(p["building_area_m2"]) if p["building_area_m2"] else None,
         "failed": p["failed_count"], "case_no": p["case_no"], "unit": _unit(p.get("address")),
         "court": COURT_NAME.get(p["court_code"], p["court_code"])}
        for p in peers
    ]  # fmt: skip
    if not auctions and not sale and not lease:
        return None
    return {
        "auctions": auctions,
        "trend": trend,
        "quarters": [
            {"q": k, "price_krw": _median(v), "n": len(v)} for k, v in sorted(quarters.items())
        ][-8:],
    }


@memo()
def detail(item_id: str, today: date) -> dict[str, Any] | None:
    """여러 조회를 한 번에 묶어 보냄(pipeline) — DB 왕복이 8번에서 1번으로 줄어 빨라짐(10/20)."""
    item_no = int(str(item_id).rsplit("-", 1)[-1] or 1)
    with connect() as c:
        with c.pipeline():
            q_item = c.execute(_ITEM_SQL, (item_id,))
            q_rounds = c.execute(
                "select sale_date, min_price_krw, result from core.rounds where item_id = %s order by sale_date",
                (item_id,),
            )
            q_events = c.execute(
                f"""select event_date::text as date, category, importance, text_masked as text, after_deadline
                   from core.case_events where case_id = {_CASE} and importance in ('high', 'mid')
                   order by event_date desc nulls last limit 12""",
                (item_id,),
            )
            q_tenants = c.execute(
                f"""select name_masked as name, occupied_part as part, move_in_date::text as move_in,
                          fixed_date::text as fixed, claim_date::text as claim, deposit_krw, monthly_rent_krw
                   from core.tenants where case_id = {_CASE} order by move_in_date nulls last""",
                (item_id,),
            )
            q_red = c.execute(
                "select value -> (select c.court_code from core.items i join core.cases c using (case_id) "
                "where i.item_id = %s) as v from ref.rule_tables where rule_key = 'court_reduction_pct' "
                "and valid_from <= %s order by valid_from desc limit 1",
                (item_id, today),
            )
            q_spec = c.execute(
                f"select payload, fetched_at from raw.court_doc_raw where case_id = {_CASE} "
                "and doc_kind = %s order by fetched_at desc limit 1",
                (item_id, f"item_detail_{item_no}"),
            )
            q_docs = c.execute(
                f"select doc_kind, max(fetched_at) as t from raw.court_doc_raw where case_id = {_CASE} group by 1",
                (item_id,),
            )
            q_hol = c.execute(
                "select holiday_date from ref.holidays where checked and holiday_date >= %s",
                (today,),
            )
            # 같은 단지(같은 법정동·지번) 실거래 2년 — 추이(10/27)
            q_trades = c.execute(
                """select t.deal_kind, t.deal_date, t.price_krw, t.deposit_krw, t.monthly_rent_krw, t.area_m2
                   from core.trades t join core.items i on i.region_code = t.region_code and i.lot_no = t.lot_no
                   where i.item_id = %s and t.deal_date >= %s""",
                (item_id, today - timedelta(days=730)),
            )
            # 같은 단지 지난 낙찰(같은 동 이름·지번이 주소에 있는 매각 결과, 이 사건은 빼고)
            q_peers = c.execute(_PEERS_SQL, (item_id,))
        r = q_item.fetchone()
        if not r:
            return None
        rounds = q_rounds.fetchall()
        events = q_events.fetchall()
        tenants = q_tenants.fetchall()
        red = q_red.fetchone()
        sp = q_spec.fetchone()
        doc_times = {x["doc_kind"]: x["t"] for x in q_docs.fetchall()}
        hol = [x["holiday_date"] for x in q_hol.fetchall()]
        trades = q_trades.fetchall()
        peers = q_peers.fetchall()
    spec, spec_at = (spec_sheet(sp["payload"]), sp["fetched_at"]) if sp else (None, None)
    if spec_at:
        doc_times["spec_sheet"] = spec_at
    out = build_detail(
        r, rounds, events, tenants, red["v"] if red else None, today, hol, doc_times, spec
    )
    cx = build_complex(trades, peers, c_area(r), today)
    for q in out["questions"]:
        if q["key"] == "worth":
            q["body"]["complex"] = cx
    return out


def bid_check(item_id: str, bid_krw: int) -> dict[str, Any] | None:
    """입찰표 점검(BID-01). 재매각이면 보증금 20%로 봅니다(법원 공고로 확인)."""
    from aucs_rules.bid_form_check import check

    with connect() as c:
        r = c.execute(
            "select min_price_krw, note_masked from core.items where item_id = %s and display_policy = 'public'",
            (item_id,),
        ).fetchone()
    if not r or not r["min_price_krw"]:
        return None
    resale = "재매각" in (r["note_masked"] or "")
    res = check(bid_krw, r["min_price_krw"], deposit_rate_pct=20 if resale else 10, resale=resale)
    return {**res.value, "status": str(res.status)}


_CALC_SQL = """
select i.item_id, i.sido, i.address, i.appraisal_krw, i.min_price_krw, i.building_area_m2, i.note_masked,
       a.result -> 'sale_rate' as sale_rate, a.result -> 'court_cell' as court_cell,
       a.result -> 'local_peers' as local_peers, a.result -> 'new_item' as new_item,
       a.result -> 'market' as market, a.result -> 'signals' as signals, a.result -> 'building' as building
from core.items i
left join lateral (select result from analysis.item_analysis x where x.item_id = i.item_id order by version desc limit 1) a on true
where i.item_id = %s and i.display_policy = 'public'
"""
_LEASE_SQL = """
select t.deposit_krw, t.monthly_rent_krw, t.area_m2 from core.trades t
join core.items i on i.region_code = t.region_code and i.lot_no = t.lot_no
where i.item_id = %s and t.deal_kind = 'lease' and t.deal_date >= current_date - 366 and t.deposit_krw > 0
"""
_TABLE_KEYS = (
    "regulated_areas",
    "loan_ltv",
    "acquisition_tax",
    "dsr",
    "first_home_relief",
    "move_out_repair",
)


def _rent(
    sel: dict[str, Any],
    cls: str,
    leases: list[dict[str, Any]],
    area: float | None,
    tables: dict[str, Any],
    fn: Any,
) -> dict[str, Any] | None:
    """세놓으면: 같은 단지(전용 ±3㎡) 1년 전세·월세 가운데 값으로."""
    near = [
        x for x in leases if not area or (x["area_m2"] and abs(float(x["area_m2"]) - area) <= 3)
    ]
    jeonse = [x["deposit_krw"] for x in near if not x["monthly_rent_krw"]]
    wolse = [x for x in near if x["monthly_rent_krw"]]
    rate = float((tables.get("dsr") or {}).get("base_rate_pct") or 4.5)
    out = fn(
        sel["total_krw"], cls=cls, loan_krw=sel["loan_krw"], rate_pct=rate, jeonse_krw=_median(jeonse),
        wolse_deposit_krw=_median([x["deposit_krw"] for x in wolse]),
        wolse_rent_krw=_median([x["monthly_rent_krw"] for x in wolse]),
    )  # fmt: skip
    res: dict[str, Any] | None = out
    if res:
        res.update(jeonse_n=len(jeonse), wolse_n=len(wolse), rate_pct=rate)
    return res


def build_calc(
    r: dict[str, Any],
    tables: dict[str, Any],
    *,
    bid_krw: int | None,
    homes: int,
    first_time: bool,
    loan_krw: int | None,
    selling: bool = False,
    income_krw: int | None = None,
    other_monthly_krw: int = 0,
    leases: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """CALC-01 묶음(순수 함수): 세 경우·고른 입찰가의 필요한 현금·이 금액 넘으면 시세보다 비싸게 사는 선."""
    from aucs_rules.calc import area_class, bid_cases, cash_needed
    from aucs_rules.costs import move_out_cost, rent_returns, repair_cost

    app, mn = r["appraisal_krw"], r["min_price_krw"]
    mkt = (r.get("market") or {}).get("price_krw")
    cls = area_class(r.get("sido"), r.get("address"), tables["regulated_areas"])
    area = float(r["building_area_m2"]) if r.get("building_area_m2") else None
    resale = "재매각" in (r.get("note_masked") or "")
    # 명도비·수리비 대략(10/27): 건축물대장의 층·승강기·연식으로. 표가 없으면 빼고 계산
    mr = tables.get("move_out_repair")
    b = r.get("building") or {}
    move = (
        move_out_cost(area, floor=b.get("unit_floor"), elevators=b.get("elevators"), table=mr)
        if mr
        else None
    )
    repair = repair_cost(area, age_years=b.get("age_years"), table=mr) if mr else None
    common = {
        "min_price_krw": mn, "appraisal_krw": app, "market_krw": mkt, "area_m2": area, "cls": cls,
        "homes": homes, "first_time": first_time, "deposit_rate_pct": 20 if resale else 10, "tables": tables,
        "selling": selling, "income_krw": income_krw, "other_monthly_krw": other_monthly_krw,
        "move_out_krw": move["mid_krw"] if move else 0, "repair_krw": repair["mid_krw"] if repair else 0,
    }  # fmt: skip
    _, _, rate = worth(r, r.get("signals") or [])
    cases = []
    if rate and app and not r.get("new_item"):
        for c in bid_cases(app, mn, rate["p25"], rate["p50"], rate["p75"]):
            v = cash_needed(c["bid_krw"], loan_override_krw=loan_krw, **common).value
            cases.append({**c, "cash_krw": v["cash_krw"]})
    bid = bid_krw or (cases[1]["bid_krw"] if cases else mn)
    sel = cash_needed(bid, loan_override_krw=loan_krw, **common).value
    cap = None
    if mkt:
        at = cash_needed(mkt, **common).value
        cap = (
            mkt
            - at["tax"]["tax_krw"]
            - at["registration_krw"]
            - at["move_out_krw"]
            - at["repair_krw"]
        )
    return {
        "cls": cls,
        "cases": cases,
        "selected": sel,
        "rent": _rent(sel, cls, leases or [], area, tables, rent_returns),
        "move_out": move,
        "repair": repair,
        "cap_krw": cap,
        "slider": {"min": mn, "max": max(int(mn * 1.6), int((cap or 0) * 1.1)), "step": 1_000_000},
        "resale": resale,
    }


@memo()
def calc(
    item_id: str,
    *,
    bid_krw: int | None,
    homes: int,
    first_time: bool,
    loan_krw: int | None,
    selling: bool = False,
    income_krw: int | None = None,
    other_monthly_krw: int = 0,
) -> dict[str, Any] | None:
    with connect() as c:
        qs = batch(
            c,
            [(_CALC_SQL, (item_id,))]
            + [
                (
                    "select value from ref.rule_tables where rule_key = %s and valid_from <= current_date "
                    "order by valid_from desc limit 1",
                    (k,),
                )
                for k in _TABLE_KEYS
            ]
            + [(_LEASE_SQL, (item_id,))],  # 세놓으면(같은 단지 전월세 1년)
        )
        r = qs[0].fetchone()
        if not r or not r["min_price_krw"]:
            return None
        n = len(_TABLE_KEYS)
        tables = {
            k: _one(q.fetchone())["value"] for k, q in zip(_TABLE_KEYS, qs[1 : n + 1], strict=True)
        }
        leases = qs[n + 1].fetchall()
    return build_calc(
        r, tables, bid_krw=bid_krw, homes=homes, first_time=first_time, loan_krw=loan_krw,
        selling=selling, income_krw=income_krw, other_monthly_krw=other_monthly_krw, leases=leases,
    )  # fmt: skip


def bid_day(item_id: str, today: date) -> dict[str, Any] | None:
    """입찰일 아침(BID-02): 법원·시각·장소·보증금·당일 바뀐 것. 시각·전화는 법원 목록 원본에서."""
    with connect() as c:
        r = c.execute(
            """select i.item_id, i.item_no, i.sale_date, i.sale_place, i.min_price_krw, i.note_masked,
                      i.status_code, i.checked_at, i.doc_key, c.court_code, c.case_no, c.dept_name
               from core.items i join core.cases c using (case_id)
               where i.item_id = %s and i.display_policy = 'public'""",
            (item_id,),
        ).fetchone()
        if not r:
            return None
        raw = c.execute(
            """select payload ->> 'maeHh1' as hh, payload ->> 'tel' as tel, payload ->> 'jiwonNm' as court_full
               from raw.court_item_raw where court_code = %s and doc_key = %s
               order by fetched_at desc limit 1""",
            (r["court_code"], r["doc_key"]),
        ).fetchone()
    hh = (raw or {}).get("hh") or ""
    resale = "재매각" in (r["note_masked"] or "")
    mn = r["min_price_krw"] or 0
    rate = 20 if resale else 10
    gone = r["status_code"] == "gone"
    sd = r["sale_date"]
    if gone:
        state, line = (
            "gone",
            "법원 목록에서 빠졌어요 · 오늘 진행하지 않을 수 있어요 · 법원에 확인하세요",
        )
    elif sd and sd > today:
        when = "내일" if (sd - today).days == 1 else f"{(sd - today).days}일 뒤"
        state, line = (
            "soon",
            f"입찰일은 {sd.month}/{sd.day}({when})이에요 · 법원 목록 기준 예정대로",
        )
    elif sd and sd < today:
        state, line = "moved", f"매각기일({sd.isoformat()})이 지났어요"
    else:
        state, line = "ok", "법원 목록 기준 오늘 진행 예정이에요"
    return {
        "item_id": r["item_id"],
        "court": COURT_NAME.get(r["court_code"], r["court_code"]),
        "court_full": (raw or {}).get("court_full")
        or COURT_NAME.get(r["court_code"], r["court_code"]),
        "dept": r["dept_name"],
        "tel": (raw or {}).get("tel"),
        "case_no": r["case_no"],
        "item_no": r["item_no"],
        "sale_date": sd.isoformat() if sd else None,
        "time": f"{hh[:2]}:{hh[2:]}" if len(hh) == 4 else None,
        "place": r["sale_place"],
        "min_price_krw": mn,
        "deposit_krw": -(-mn * rate // 100),
        "deposit_rate_pct": rate,
        "resale": resale,
        "state": state,
        "state_line": line,
        "checked_at": r["checked_at"].strftime("%m/%d %H:%M") if r["checked_at"] else None,
    }
