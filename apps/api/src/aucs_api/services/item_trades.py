"""실거래 전체 보기(11/21 대표님): 같은 단지(같은 법정동 · 지번)의 매매를 2006년부터.

- 해마다: core.trade_yearly(PC 에 받아 둔 지난 자료 요약, jobs/trade_summary.py) — 신고 건수 · 중간값 · 최저 · 최고.
  값은 튀는 거래를 시세 계산과 같은 규칙(사분위 범위 1.5배 밖)으로 뺀 뒤(11/21 대표님).
- 최근 2년 한 건씩: core.trades(매월 수집 원본) — 날짜 · 층 · 값, 전세 · 월세도.
- 같은 단지 지난 낙찰: item_complex.PEERS_SQL(상세 「같은 단지 지난 낙찰」과 같은 셈).
물건 종류에 맞는 거래만 — 시세 계산(workers analyze.trade_type)과 같은 나눔: 아파트 → apt · 오피스텔 → officetel ·
다세대 / 연립주택,다세대,빌라 → rowhouse, 그 밖(상가 · 근린 · 단독 등)은 없음. 한 지번에 아파트와 상가가 같이 있어도
상가 물건에 아파트 값이 나오지 않게(11/21 — 진행 물건 중 상가 · 오피스텔 · 근린 234건이 같은 지번 아파트 거래에 걸렸음).
면적은 ㎡ 반올림으로 묶음 — 물건 면적에 가장 가까운 것(±3㎡ 안)을 먼저 보여 주고, 없으면 거래가 가장 많은 면적.
"""

from datetime import date, timedelta
from typing import Any

from aucs_api.db import connect
from aucs_api.services.item_complex import PEERS_SQL, _unit

_LOT = "region_code = left(%(rc)s, 8) || '00' and lot_no = %(lot)s"

# core.items 한 줄(i) → 실거래 종류. workers jobs/analyze.py trade_type 과 같게 둘 것
KIND_SQL = """case when i.usage_name = '아파트' then 'apt'
  when i.usage_name = '오피스텔' or (i.usage_name = '상가,오피스텔,근린시설' and i.building_desc like '%%오피스텔%%') then 'officetel'
  when i.usage_name in ('다세대', '연립주택,다세대,빌라') then 'rowhouse' end"""


def pick_area(areas: list[dict[str, Any]], item_area: float | None, want: int | None) -> int | None:
    """보여 줄 면적(순수 함수): 고른 것 → 물건 면적에 가장 가까운 것(±3㎡) → 거래가 가장 많은 것."""
    have = [a["area"] for a in areas]
    if want in have:
        return want
    if item_area:
        near = [a for a in have if abs(a - item_area) <= 3]
        if near:
            return min(near, key=lambda a: abs(a - item_area))
    return max(areas, key=lambda a: a["n"])["area"] if areas else None


def item_trades(item_id: str, want: int | None, today: date) -> dict[str, Any] | None:
    with connect() as c:
        it = c.execute(
            f"""select i.region_code as rc, i.lot_no as lot, i.building_area_m2, {KIND_SQL} as prop
                from core.items i where i.item_id = %s""",
            (item_id,),
        ).fetchone()
        if not it or not it["rc"] or not it["lot"] or not it["prop"]:
            return None
        areas = c.execute(
            f"""select area_m2 as area, sum(n_all)::int as n from core.trade_yearly
                where {_LOT} and prop_type = %(prop)s group by 1 order by 1""",
            it,
        ).fetchall()
        area = pick_area(areas, float(it["building_area_m2"] or 0) or None, want)
        if area is None:
            return {"areas": [], "area": None, "years": [], "recent": [], "auctions": []}
        head = c.execute(
            f"""select string_agg(distinct names, ' · ') as name, max(build_year) as built,
                       max(last_month) as last
                from core.trade_yearly where {_LOT} and prop_type = %(prop)s""",
            it,
        ).fetchone()
        years = c.execute(
            f"""select y, n_all as n, n as kept, mid_krw as mid, low_krw as low, high_krw as high
                from core.trade_yearly
                where {_LOT} and prop_type = %(prop)s and area_m2 = %(area)s order by y""",
            {**it, "area": area},
        ).fetchall()
        recent = c.execute(
            f"""select deal_kind as kind, deal_date as date, floor, price_krw as price,
                       deposit_krw as deposit, monthly_rent_krw as rent
                from core.trades where {_LOT} and prop_type = %(prop)s and round(area_m2) = %(area)s
                  and deal_date >= %(since)s
                order by deal_date desc limit 1000""",
            {**it, "area": area, "since": today - timedelta(days=730)},
        ).fetchall()
        peers = c.execute(PEERS_SQL, (item_id,)).fetchall()
    return {
        "name": " · ".join(sorted({x for x in (head["name"] or "").split(" · ") if x})) or None,
        "built": head["built"],
        "last": head["last"].isoformat()[:7] if head["last"] else None,
        "areas": areas,
        "area": area,
        "years": years,
        "recent": [{**r, "date": r["date"].isoformat()} for r in recent],
        "auctions": [
            {
                "date": p["sale_date"].isoformat(),
                "price": p["winning_bid_krw"],
                "area": float(p["building_area_m2"]) if p["building_area_m2"] else None,
                "unit": _unit(p["address"]),
            }
            for p in peers
        ],
    }
