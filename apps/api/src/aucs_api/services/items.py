"""물건 카드·지역 목록 (공개 화면용). display_policy = public 만, 이름은 가린 값만 내보냅니다."""

import re
from datetime import date
from typing import Any

from aucs_rules.find_filter import ANALYSIS_JOIN, COURT_VISIBLE, VEHICLES, court_where

from aucs_api.db import batch, connect

COURT_NAME = {
    "B000210": "서울중앙", "B000211": "서울동부", "B000215": "서울서부", "B000212": "서울남부",
    "B000213": "서울북부", "B000214": "의정부", "B214807": "고양", "B214804": "남양주",
    "B000241": "부천", "B000250": "수원", "B000251": "성남", "B000252": "여주",
    "B000253": "평택", "B250826": "안산", "B000254": "안양", "B000240": "인천",
}  # fmt: skip

_CARD_SQL = f"""
select i.item_id, c.court_code, c.case_no, i.sale_date, i.usage_name, i.sido, i.sigungu, i.gu, i.address,
       i.building_desc, i.building_area_m2, i.appraisal_krw, i.min_price_krw, i.failed_count, i.is_share,
       st_y(i.geom::geometry) as lat, st_x(i.geom::geometry) as lon,
       a.result -> 'top' as top, a.result -> 'signals' as signals,
       coalesce((select json_object_agg(d.data_kind, d.status) from analysis.item_data_status d where d.item_id = i.item_id), '{{}}') as data_status
from core.items i
join core.cases c using (case_id)
{ANALYSIS_JOIN}
where {COURT_VISIBLE}
"""  # 보이는 물건 조건(공개·부동산·목록에 있음·분석 끝)은 규칙 FIND-03 한 곳(11/8)


def card(r: dict[str, Any], today: date) -> dict[str, Any]:
    """DB 한 줄 → 카드 한 장 (계산은 여기서 한 번만)."""
    app, mn = r["appraisal_krw"], r["min_price_krw"]
    signals = r["signals"] or []
    unknown = [s for s in signals if s.get("status") == "모름"]
    flagged = [
        s
        for s in signals
        if s.get("level") in ("fatal", "high", "mid") and s.get("status") != "모름"
    ]
    return {
        "item_id": r["item_id"],
        "source": "court",
        "court": COURT_NAME.get(r["court_code"], r["court_code"]),
        "case_no": r["case_no"],
        "sale_date": r["sale_date"].isoformat() if r["sale_date"] else None,
        "d_day": (r["sale_date"] - today).days if r["sale_date"] else None,
        "usage": r["usage_name"],
        "place": " ".join(x for x in [r["sigungu"], r["gu"]] if x),
        "building": r["building_desc"],
        "area_m2": float(r["building_area_m2"]) if r["building_area_m2"] else None,
        "appraisal_krw": app,
        "min_price_krw": mn,
        "min_rate": round(mn * 100 / app) if app and mn else None,
        "deposit_krw": mn // 10
        if mn
        else None,  # 입찰보증금(보통 최저가 10%) — 재매각·특별조건은 상세에서
        "failed_count": r["failed_count"],
        "below_appraisal_krw": app - mn if app and mn and app > mn else 0,
        "lat": r["lat"],
        "lon": r["lon"],
        "top_signal": flagged[0] if flagged else None,
        "unknown_count": len(unknown),
        "data_status": r["data_status"],
    }


def parse_query(q: str | None) -> dict[str, Any] | None:
    """검색어 → 찾는 방법. 사건번호(2025타경55580·25-55580·55580) / 글자(단지·동네·주소)."""
    t = re.sub(r"\s+", "", q or "")
    if not t:
        return None
    if m := re.fullmatch(r"(\d{2}|\d{4})(?:타경|-)(\d{1,7})", t):
        year = m.group(1) if len(m.group(1)) == 4 else "20" + m.group(1)
        return {"kind": "case", "case_no": f"{year}타경{int(m.group(2))}"}
    if re.fullmatch(r"\d{3,7}", t):
        return {"kind": "case_suffix", "suffix": f"타경{int(t)}"}
    return {"kind": "text", "text": t}


def _q_where(
    pq: dict[str, Any] | None, case_col: str, text_cols: list[str], params: dict[str, Any]
) -> str:
    """검색 조건 SQL 조각 (글자는 띄어쓰기를 빼고 비교)."""
    if pq is None:
        return ""
    if pq["kind"] == "case":
        params["case_no"] = pq["case_no"]
        return f" and {case_col} = %(case_no)s"
    if pq["kind"] == "case_suffix":
        params["suffix"] = "%" + pq["suffix"]
        return f" and {case_col} like %(suffix)s"
    params["text"] = "%" + pq["text"] + "%"
    ors = " or ".join(f"replace(coalesce({c}, ''), ' ', '') ilike %(text)s" for c in text_cols)
    return f" and ({ors})"


def short_address(a: str | None) -> str:
    """「경기도 용인시 수지구 성복동 …」 → 「용인시 수지구 성복동」 (시도는 뺌)."""
    w = (a or "").replace(",", " ").split()
    return " ".join(w[1:4]) if len(w) > 1 else (a or "")


RESULT_GROUPS = {"sold": ("sold",), "withdrawn": ("withdrawn", "dismissed", "changed")}
RESULT_KO = {
    "sold": "매각",
    "failed": "유찰",
    "changed": "변경",
    "withdrawn": "취하",
    "dismissed": "기각",
}


def search_results(*, q: str | None, status: str, sigungu: list[str], limit: int) -> dict[str, Any]:
    """끝난 사건(매각·취하·변경…) 찾기. 같은 물건은 가장 최근 결과 하나."""
    pq = parse_query(q)
    params: dict[str, Any] = {"limit": limit}
    kinds = RESULT_GROUPS.get(status)
    where = f"s.display_policy = 'public' and coalesce(s.usage_name, '') !~ '{VEHICLES}'"
    if kinds:
        where += " and s.result = any(%(kinds)s)"
        params["kinds"] = list(kinds)
    if sigungu and pq is None:
        # 매각결과는 물건 표에 없는 사건이 많아 주소 글자로도 지역을 맞춤
        where += " and (i.sigungu = any(%(sigungu)s) or s.address ilike any(%(sg_like)s))"
        params["sigungu"] = sigungu
        params["sg_like"] = [f"%{x}%" for x in sigungu]
    where += _q_where(pq, "s.case_no", ["i.building_desc", "s.address"], params)
    sql = f"""
      select distinct on (s.court_code, s.case_no, s.item_no)
             s.result_id, s.item_id, s.court_code, s.case_no, s.sale_date, s.result, s.usage_name,
             s.appraisal_krw, s.winning_bid_krw, s.sale_rate, i.sigungu, i.gu, i.building_desc,
             s.address, i.item_id as live_item_id
      from core.sale_results s left join core.items i on i.item_id = s.item_id
      where {where}
      order by s.court_code, s.case_no, s.item_no, s.sale_date desc"""
    with connect() as c:
        rows = c.execute(
            f"select * from ({sql}) x order by sale_date desc limit %(limit)s", params
        ).fetchall()
    return {"results": [
        {
            "result_id": r["result_id"], "item_id": r["live_item_id"],
            "court": COURT_NAME.get(r["court_code"], r["court_code"]), "case_no": r["case_no"],
            "sale_date": r["sale_date"].isoformat(), "result": RESULT_KO.get(r["result"], r["result"]),
            "usage": r["usage_name"],
            "place": " ".join(x for x in [r["sigungu"], r["gu"]] if x) or short_address(r["address"]),
            "building": r["building_desc"], "appraisal_krw": r["appraisal_krw"],
            "winning_bid_krw": r["winning_bid_krw"],
            "sale_rate": round(float(r["sale_rate"])) if r["sale_rate"] is not None else None,
        }
        for r in rows
    ]}  # fmt: skip


def list_items(
    *,
    sigungu: list[str],
    max_cash: int | None,
    sort: str,
    limit: int,
    today: date,
    q: str | None = None,
    extra: dict[str, Any] | None = None,
    source: str = "all",
) -> dict[str, Any]:
    """진행 중 물건. source: all(경매·공매 함께, 기본) · court · onbid (10/28 공매)."""
    from aucs_api.services import onbid

    queries: list[tuple[str, dict[str, Any]]] = []
    if source in ("all", "court"):
        queries += _court_query(sigungu, max_cash, sort, limit, today, q, extra)
    oq = (
        onbid.build_query(sigungu=sigungu, max_cash=max_cash, q=q, extra=extra, today=today)
        if source in ("all", "onbid")
        else None
    )
    if oq:
        osql, op = oq
        op["limit"] = limit
        queries += [
            (
                osql
                + f" order by {onbid.ORDER.get(sort, onbid.ORDER['deadline'])} limit %(limit)s",
                op,
            ),
            ("select count(*) as n from (" + osql + ") q", op),
        ]
    if not queries:
        return {"total": 0, "items": [], "exact_item_id": None}
    with connect() as c:
        res = batch(c, queries)
    court_items: list[dict[str, Any]] = []
    onbid_items: list[dict[str, Any]] = []
    total = 0
    i = 0
    if source in ("all", "court"):
        court_items = [card(r, today) for r in res[0].fetchall()]
        total += (res[1].fetchone() or {"n": 0})["n"]
        i = 2
    if oq:
        onbid_items = [onbid.onbid_card(r, today) for r in res[i].fetchall()]
        total += (res[i + 1].fetchone() or {"n": 0})["n"]
    items = onbid.merge(court_items, onbid_items, sort, limit)
    pq = parse_query(q)
    exact = None
    if (
        len(items) == 1
        and pq is not None
        and (pq["kind"] == "case" or items[0]["source"] == "onbid")
    ):
        exact = items[0]["item_id"]
    return {"total": total, "items": items, "exact_item_id": exact}


def _court_query(
    sigungu: list[str],
    max_cash: int | None,
    sort: str,
    limit: int,
    today: date,
    q: str | None,
    extra: dict[str, Any] | None,
) -> list[tuple[str, dict[str, Any]]]:
    """경매 물건 목록 SQL 과 건수 SQL. 공매 물건관리번호 검색이면 빈 목록."""
    if q and re.fullmatch(r"\d{4}-\d{4,5}-\d{3,6}", re.sub(r"\s+", "", q)):
        return []
    pq = parse_query(q)
    if pq is not None:  # 검색할 때는 시작 질문의 지역·현금 조건을 빼고 찾음
        sigungu, max_cash = [], None
    # 찾기 조건(FIND-03): 지역·현금·조건 칸 모두 전문가 표·알림과 같은 규칙 한 곳
    more, params = court_where({**(extra or {}), "sigungu": sigungu, "max_cash": max_cash}, today)
    params["limit"] = limit
    sql = _CARD_SQL + more
    if pq is not None:
        sql += _q_where(pq, "c.case_no", ["i.building_desc", "i.address"], params)
    order = {
        "deadline": "i.sale_date, i.item_id",
        "rate": "i.min_price_krw::float / nullif(i.appraisal_krw, 0), i.sale_date",
    }
    count_sql = "select count(*) as n from (" + sql + ") q"
    sql += f" order by {order.get(sort, order['deadline'])} limit %(limit)s"
    return [(sql, params), (count_sql, params)]


def regions() -> list[dict[str, Any]]:
    """시작 질문의 지역 고르기: 서울·경기·인천 시군구와 지금 진행 중인 물건 수(인천 11/4)."""
    with connect() as c:
        return c.execute(
            """select r.sido, r.sigungu, count(i.item_id) as items
               from (select distinct sido, split_part(sigungu, ' ', 1) as sigungu from ref.regions
                     where level = 'sigungu' and sido in ('서울특별시', '경기도', '인천광역시')) r
               left join core.items i on i.sido = r.sido and i.sigungu = r.sigungu and i.sale_date >= current_date
                 and i.status_code is distinct from 'gone'
                 and exists (select 1 from analysis.item_analysis x where x.item_id = i.item_id)
               group by 1, 2
               order by array_position(array['서울특별시', '경기도', '인천광역시'], r.sido), 2"""
        ).fetchall()


def request_docs(item_id: str) -> bool:
    """손님이 연 물건에 현황조사·문건이 없으면 그 사건 서류 받기를 줄 세움(11/4) — PC 수집기가 5분마다 받아 감.

    같은 물건은 하루에 한 번만, 이미 받았으면 줄 세우지 않음. 줄 세웠으면 True.
    """
    key = f"case_docs:{item_id}"
    with connect() as c:
        row = c.execute(
            """insert into ops.job_requests (job_key)
               select %(key)s
               where exists (select 1 from core.items where item_id = %(id)s and sale_date >= current_date)
                 and not exists (select 1 from analysis.item_data_status d where d.item_id = %(id)s
                                 and d.data_kind = 'status_report' and d.status in ('extracted', 'verified'))
                 and not exists (select 1 from ops.job_requests r where r.job_key = %(key)s
                                 and (r.status in ('waiting', 'running') or r.requested_at > now() - interval '1 day'))
               returning req_id""",
            {"key": key, "id": item_id},
        ).fetchone()
    return row is not None
