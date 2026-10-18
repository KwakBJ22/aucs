"""물건 카드·지역 목록 (공개 화면용). display_policy = public 만, 이름은 가린 값만 내보냅니다."""

from datetime import date
from typing import Any

from aucs_api.db import connect

COURT_NAME = {
    "B000210": "서울중앙", "B000211": "서울동부", "B000215": "서울서부", "B000212": "서울남부",
    "B000213": "서울북부", "B000214": "의정부", "B214807": "고양", "B214804": "남양주",
    "B000241": "부천", "B000250": "수원", "B000251": "성남", "B000252": "여주",
    "B000253": "평택", "B250826": "안산", "B000254": "안양",
}  # fmt: skip

_CARD_SQL = """
select i.item_id, c.court_code, c.case_no, i.sale_date, i.usage_name, i.sido, i.sigungu, i.gu, i.address,
       i.building_desc, i.building_area_m2, i.appraisal_krw, i.min_price_krw, i.failed_count, i.is_share,
       st_y(i.geom::geometry) as lat, st_x(i.geom::geometry) as lon,
       a.result -> 'top' as top, a.result -> 'signals' as signals,
       coalesce((select json_object_agg(d.data_kind, d.status) from analysis.item_data_status d where d.item_id = i.item_id), '{}') as data_status
from core.items i
join core.cases c using (case_id)
left join lateral (select result from analysis.item_analysis x where x.item_id = i.item_id order by version desc limit 1) a on true
where i.display_policy = 'public' and i.sale_date >= %(today)s
  and a.result is not null  -- 분석이 끝난 물건만 손님에게 보임(10/18 대표님)
"""


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


def list_items(
    *, sigungu: list[str], max_cash: int | None, sort: str, limit: int, today: date
) -> dict[str, Any]:
    sql = _CARD_SQL
    params: dict[str, Any] = {"today": today, "limit": limit}
    if sigungu:
        sql += " and i.sigungu = any(%(sigungu)s)"
        params["sigungu"] = sigungu
    if max_cash:
        # 임시 기준(2단계): 입찰보증금(최저가 10%)을 낼 수 있는 물건. 필요한 현금 전체 계산은 3단계 CALC-01
        sql += " and i.min_price_krw / 10 <= %(max_cash)s"
        params["max_cash"] = max_cash
    order = {
        "deadline": "i.sale_date, i.item_id",
        "rate": "i.min_price_krw::float / nullif(i.appraisal_krw, 0), i.sale_date",
    }
    count_sql = "select count(*) as n from (" + sql + ") q"
    sql += f" order by {order.get(sort, order['deadline'])} limit %(limit)s"
    with connect() as c:
        rows = c.execute(sql, params).fetchall()
        total = c.execute(count_sql, params).fetchone()
    return {"total": total["n"] if total else 0, "items": [card(r, today) for r in rows]}


def regions() -> list[dict[str, Any]]:
    """시작 질문의 지역 고르기: 서울·경기 시군구와 지금 진행 중인 물건 수."""
    with connect() as c:
        return c.execute(
            """select r.sido, r.sigungu, count(i.item_id) as items
               from (select distinct sido, split_part(sigungu, ' ', 1) as sigungu from ref.regions
                     where level = 'sigungu' and sido in ('서울특별시', '경기도')) r
               left join core.items i on i.sido = r.sido and i.sigungu = r.sigungu and i.sale_date >= current_date
                 and exists (select 1 from analysis.item_analysis x where x.item_id = i.item_id)
               group by 1, 2 order by 1 desc, 2"""
        ).fetchall()
