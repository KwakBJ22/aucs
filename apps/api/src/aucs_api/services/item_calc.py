"""「얼마가 드나」: 입찰가 계산·입찰표 검사·입찰일 아침"""

from datetime import date
from typing import Any

from aucs_api.cache import memo
from aucs_api.db import batch, connect
from aucs_api.services.item_complex import median
from aucs_api.services.item_worth import worth
from aucs_api.services.items import COURT_NAME


def _one(r: dict[str, Any] | None) -> dict[str, Any]:
    """꼭 있어야 하는 한 줄(기준표 등). 없으면 설정 오류라 바로 알림."""
    if r is None:
        raise LookupError("기준표가 비어 있어요")
    return r


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
        sel["total_krw"], cls=cls, loan_krw=sel["loan_krw"], rate_pct=rate, jeonse_krw=median(jeonse),
        wolse_deposit_krw=median([x["deposit_krw"] for x in wolse]),
        wolse_rent_krw=median([x["monthly_rent_krw"] for x in wolse]),
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
