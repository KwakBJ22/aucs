"""물건 상세(ITEM-01 다섯 질문). DB에서 모으는 부분과 화면 묶음을 만드는 부분(순수 함수)을 나눴습니다."""

from datetime import date, timedelta
from typing import Any

from aucs_rules.appraisal_parts import appraisal_parts
from aucs_rules.appraisal_points import parse_points
from aucs_rules.find_filter import VEHICLES
from aucs_rules.fmt import won
from aucs_rules.risk import FAILURE_TYPES
from aucs_rules.sale_rate import next_round_min_price
from aucs_rules.schedule import after_sale

from aucs_api import settings
from aucs_api.cache import memo
from aucs_api.db import connect
from aucs_api.services.checklist import DONE, build_checklist, build_flow
from aucs_api.services.court_stats import court_bidders
from aucs_api.services.docs import spec_sheet, spec_text
from aucs_api.services.fail_odds import odds_for
from aucs_api.services.interest import interest
from aucs_api.services.item_buy import building_lines
from aucs_api.services.item_complex import PEERS_SQL, build_complex, c_area
from aucs_api.services.item_links import same_house
from aucs_api.services.item_text import GONE_LINE, PENDING, RESULT_KO, TAGS, failure_table, verdict
from aucs_api.services.item_worth import appraisal_gap, worth
from aucs_api.services.items import card, photo_url
from aucs_api.services.picks import reduction_table

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
where i.item_id = %(id)s and i.display_policy = 'public'
  and coalesce(i.usage_name, '') !~ %(vehicles)s  -- 차·배는 다루지 않음(목록처럼 상세도 막음, 11/1)
"""


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
    sale: dict[str, Any] | None = None,
) -> dict[str, Any]:
    c = card(r, today)
    signals = r["signals"] or []
    stxt = spec_text(spec)
    rate_ans, rate_notes, rate = worth(r, signals, stxt, reduction["pct"] if reduction else None)
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
    out_come = outcome(rounds, sale, today, questions[2]["body"].get("range_krw"))
    if analyzed and any(
        x.get("ftype") == "T1" and x.get("level") in ("fatal", "high") for x in signals
    ):
        # 떠안는 돈이 있으면 시세 기준 예상 낙찰가는 그대로 믿으면 안 됨(11/1)
        questions[2]["answer"] = "떠안는 돈을 빼고 봐야 해요 · 아래 예상은 떠안는 돈이 없을 때 값"
        questions[2]["tone"] = "orange"
        questions[2]["body"]["assume_risk"] = True
    if out_come and out_come["closed"]:
        if out_come["code"] == "sold" and out_come["expected"]:
            lo, hi = out_come["expected"]
            bid = out_come["winning_bid_krw"]
            # 웹 금액(won)은 만 원 아래를 반올림 → 같은 숫자로 맞춤
            questions[2]["answer"] = f"예상 {won(_man(lo))}~{won(_man(hi))} · 실제 {won(_man(bid))}"
    return {
        **c,
        "outcome": out_come,
        "verdict": (CLOSED_LINE if out_come and out_come["closed"] else verdict(signals, len(todo)))
        if analyzed
        else PENDING,
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
            "fail_odds": None,  # 같은 법원·종류·회차 실제 유찰 비율(WAIT-01) — detail() 에서 채움
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
        "failure_table": failure_table(
            signals,
            {
                "usage": r["usage_name"],
                "ds": ds,
                "redev": bool(r.get("redev")),
                "market": bool((r.get("market") or {}).get("price_krw")),
            },
        ),  # fmt: skip
        "schedule": sched,
        "computed_at": r["computed_at"].isoformat() if r["computed_at"] else None,
    }


_CASE = "(select case_id from core.items where item_id = %s)"


def _man(v: int) -> int:
    """만 원 아래 반올림(웹 Math.round 와 같게 — 파이썬 round 는 5에서 짝수로 감)."""
    return int(v / 10_000 + 0.5) * 10_000


CLOSED_LINE = "끝난 물건이에요 · 아래는 매각 전에 한 분석이에요"


def outcome(
    rounds: list[dict[str, Any]],
    sale: dict[str, Any] | None,
    today: date,
    expected: list[int] | None,
) -> dict[str, Any] | None:
    """지난 기일 결과(11/1): 앞으로 잡힌 기일이 없고 마지막 기일이 지났으면 그 결과. 매각·취하면 끝(closed)."""
    if not rounds or any(x["sale_date"] >= today for x in rounds):
        return None
    last = rounds[-1]
    code = (sale or {}).get("result") or last["result"] or "unknown"
    if code == "scheduled":
        code = "unknown"  # 기일은 지났는데 결과를 아직 못 받음
    bid = (sale or {}).get("winning_bid_krw")
    return {
        "date": last["sale_date"].isoformat(),
        "code": code,
        "text": RESULT_KO.get(code, code),
        "closed": code in ("sold", "withdrawn"),
        "winning_bid_krw": bid,
        "rate": float(sale["sale_rate"]) if sale and sale.get("sale_rate") is not None else None,
        "expected": expected,
        "within": bool(bid and expected and expected[0] <= bid <= expected[1]),
    }


@memo()
def detail(item_id: str, today: date) -> dict[str, Any] | None:
    """여러 조회를 한 번에 묶어 보냄(pipeline) — DB 왕복이 8번에서 1번으로 줄어 빨라짐(10/20)."""
    item_no = int(str(item_id).rsplit("-", 1)[-1] or 1)
    with connect() as c:
        with c.pipeline():
            q_item = c.execute(_ITEM_SQL, {"id": item_id, "vehicles": VEHICLES})
            # 매각기일: 우리가 받은 회차 + 그 전 매각결과(11/1 — 유찰 12번 물건이 1줄만 보였음)
            q_rounds = c.execute(
                """select sale_date, min_price_krw, result from core.rounds where item_id = %(id)s
                   union all
                   select s.sale_date, s.min_price_krw, s.result from core.sale_results s
                   where s.item_id = %(id)s and not exists (select 1 from core.rounds r
                         where r.item_id = s.item_id and r.sale_date = s.sale_date)
                   order by sale_date""",
                {"id": item_id},
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
            q_spec = c.execute(
                f"select payload, fetched_at from raw.court_doc_raw where case_id = {_CASE} "
                "and doc_kind = %s order by fetched_at desc limit 1",
                (item_id, f"item_detail_{item_no}"),
            )
            q_apr = c.execute(
                f"""select distinct on (doc_kind) doc_kind, payload from raw.court_doc_raw where case_id = {_CASE}
                    and doc_kind in ('appraisal', 'appraisal_pdf') order by doc_kind, fetched_at desc""",
                (item_id,),
            )
            q_file = c.execute(
                f"select path from core.appraisal_files where case_id = {_CASE}", (item_id,)
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
                   from core.trades t join core.items i on t.region_code = left(i.region_code, 8) || '00' and i.lot_no = t.lot_no
                   where i.item_id = %s and t.deal_date >= %s""",
                (item_id, today - timedelta(days=730)),
            )
            # 같은 단지 지난 낙찰(같은 동 이름·지번이 주소에 있는 매각 결과, 이 사건은 빼고)
            q_peers = c.execute(PEERS_SQL, (item_id,))
            # 가까운 역 두 곳(직선 1.5km 안) — 상세 「역까지 걸어서」(11/12)
            q_stn = c.execute(
                """select st.name_ko as name, st.line_name as line,
                          st_y(st.geom::geometry) as lat, st_x(st.geom::geometry) as lon,
                          round(st_distance(st.geom, i.geom::geography))::int as straight_m
                   from core.items i join ref.stations st
                     on st.closed_date is null and i.geom is not null
                    and st_dwithin(st.geom, i.geom::geography, 1500)
                   where i.item_id = %s order by st.geom <-> i.geom::geography limit 6""",
                (item_id,),
            )
            q_sale = c.execute(
                """select result, winning_bid_krw, sale_rate, sale_date from core.sale_results
                   where item_id = %s order by sale_date desc limit 1""",
                (item_id,),
            )
        r = q_item.fetchone()
        if not r:
            return None
        rounds = q_rounds.fetchall()
        events = q_events.fetchall()
        tenants = q_tenants.fetchall()
        sp = q_spec.fetchone()
        apr = {x["doc_kind"]: x["payload"] or {} for x in q_apr.fetchall()}
        pdf = q_file.fetchone()
        doc_times = {x["doc_kind"]: x["t"] for x in q_docs.fetchall()}
        hol = [x["holiday_date"] for x in q_hol.fetchall()]
        trades = q_trades.fetchall()
        peers = q_peers.fetchall()
        sale = q_sale.fetchone()
        stations = q_stn.fetchall()
    spec, spec_at = (spec_sheet(sp["payload"]), sp["fetched_at"]) if sp else (None, None)
    if spec_at:
        doc_times["spec_sheet"] = spec_at
    out = build_detail(
        r,
        rounds,
        events,
        tenants,
        reduction_table(today).get(r["court_code"]),
        today,
        hol,
        doc_times,
        spec,
        sale,
    )
    out["next_round"]["fail_odds"] = odds_for(r, today)
    cx = build_complex(trades, peers, c_area(r), today)
    for q in out["questions"]:
        if q["key"] == "worth":
            q["body"]["complex"] = cx
    out["same_house"] = same_house(item_id)
    out["interest"] = interest(item_id)
    out["court_bidders"] = court_bidders(item_id)
    out["photos"] = photos(item_id)
    out["stations"] = walk_stations(stations)
    out["appraisal"] = appraisal_section(
        sp["payload"] if sp else None, apr, pdf_url(pdf["path"] if pdf else None)
    )
    return out


def walk_stations(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """가까운 역 두 곳 — 같은 역 이름(환승역 노선 여럿)은 하나로 묶어 노선을 합침(WALK-01 어림)."""
    from aucs_rules.walk import station_name, walk_estimate

    by: dict[str, dict[str, Any]] = {}
    for r in rows:
        x = by.setdefault(
            r["name"],
            {
                "name": station_name(r["name"]),
                "lines": [],
                "straight_m": r["straight_m"],
                "lat": r["lat"],
                "lon": r["lon"],
            },
        )
        if r["line"] and r["line"] not in x["lines"]:
            x["lines"].append(r["line"])
    out = []
    for x in list(by.values())[:2]:
        w = walk_estimate(x["straight_m"]).value or {}
        out.append({**x, **w})
    return out


def pdf_url(path: str | None) -> str | None:
    """감정평가서 원본 저장소 경로 → 공개 주소(11/11 대표님 — 원본 그대로 보임)."""
    if not path or not settings.SUPABASE_URL:
        return None
    return f"{settings.SUPABASE_URL}/storage/v1/object/public/appraisal-pdfs/{path}"


def appraisal_section(
    payload: dict[str, Any] | None,
    apr: dict[str, dict[str, Any]] | None = None,
    pdf: str | None = None,
) -> dict[str, Any] | None:
    """「감정평가 요점」 칸(11/4 대표님 — 개인정보 가리고 쓰기 허락, 평가사 이름을 곁에 붙임).

    법원 물건상세의 감정평가요항표 요약 글. 회사 이름은 이 자료에 없어(문건송달에도 가려져 있음)
    감정평가서 원본(kapa_pdf)을 받으면 채움 — 그 전에는 None 이고 화면은 출처만 적음. 가격시점은 법원 감정평가서 정보.
    감정가 나눔(11/7): 토지·건물 금액 · 제시외 건물 · 대지권도 같은 물건상세에서."""
    dr = (payload or {}).get("dma_result") or {}
    a = apr or {}
    # 법원 요항을 아직 못 받았으면 받아 둔 감정평가서 원본의 요항표로(11/11)
    points = parse_points(dr.get("aeeWevlMnpntLst") or (a.get("appraisal_pdf") or {}).get("points"))
    ymd = str(((a.get("appraisal") or {}).get("info") or {}).get("dspslPrcCrtrYmd") or "")
    price_date = f"{ymd[:4]}.{ymd[4:6]}.{ymd[6:8]}" if len(ymd) == 8 else None
    firm = (a.get("appraisal_pdf") or {}).get("firm")
    parts = appraisal_parts(
        dr.get("gdsDspslObjctLst"), dr.get("gdsNotSugtBldLsstAll"), dr.get("rgltLandLstAll")
    ).value
    if not points and not price_date and not parts and not pdf:
        return None
    return {
        "points": points,
        "firm": firm,
        "price_date": price_date,
        "parts": parts or None,
        "pdf_url": pdf,  # 원본이 있으면 바로 열고, 없으면 화면이 법원으로 안내(11/11)
    }


def photos(item_id: str) -> list[str]:
    """법원 현장 사진(휴대폰 크기, Storage 공개 주소). 매각 뒤 30일 지나면 지워져 빈 목록(11/1)."""
    if not settings.SUPABASE_URL:
        return []
    with connect() as c:
        rows = c.execute(
            """select p.path from core.item_photos p join core.items i using (case_id)
               where i.item_id = %s order by p.seq""",
            (item_id,),
        ).fetchall()
    return [u for r in rows if (u := photo_url(r["path"]))]
