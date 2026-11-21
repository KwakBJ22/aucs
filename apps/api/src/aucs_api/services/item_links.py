"""같은 집이 법원 경매와 공매에 함께 나온 경우(core.item_links, 공매 수집 때 채움)."""

import re
from typing import Any

from aucs_api.db import connect

_COURT_SQL = """
select i.item_id, c.case_no, i.sale_date::text as sale_date, i.min_price_krw
from core.item_links l join core.items i on i.item_id = l.court_item_id join core.cases c using (case_id)
where l.onbid_item_id = %s and i.sale_date >= current_date order by i.sale_date
"""
_ONBID_SQL = """
select o.item_id, o.mng_no, (o.bid_end at time zone 'Asia/Seoul')::date::text as bid_day, o.min_price_krw
from core.item_links l join core.onbid_items o on o.item_id = l.onbid_item_id
where l.court_item_id = %s and o.status_code = 'active' order by o.bid_end nulls last
"""


def same_house(item_id: str) -> list[dict[str, Any]]:
    """경매 물건이면 같은 집 공매, 공매 물건이면 같은 집 경매. 먼저 팔리는 쪽에서 끝나요."""
    onbid = item_id.startswith("OB-")
    with connect() as c:
        rows = c.execute(_COURT_SQL if onbid else _ONBID_SQL, (item_id,)).fetchall()
    if onbid:
        return [{"source": "court", "item_id": r["item_id"], "no": r["case_no"], "date": r["sale_date"],
                 "min_price_krw": r["min_price_krw"]} for r in rows]  # fmt: skip
    return [{"source": "onbid", "item_id": r["item_id"], "no": r["mng_no"],
             "date": r["bid_day"],
             "min_price_krw": r["min_price_krw"]} for r in rows]  # fmt: skip


# 같은 건물(같은 법정동 · 같은 지번)에서 나온 다른 경매(11/21 — 경매레이더에 있던 것).
# 빌라 한 동이 통째로 나오는 사건 · 같은 단지 다른 호를 알아보려고. 진행 중인 것만.
_BUILDING_SQL = """
select o.item_id, o.case_id, c.case_no, o.address, o.sale_date::text as sale_date, o.min_price_krw
from core.items i
join core.items o on o.region_code = i.region_code and o.lot_no = i.lot_no and o.item_id <> i.item_id
join core.cases c on c.case_id = o.case_id
where i.item_id = %s and i.lot_no is not null and i.region_code is not null
  and o.sale_date >= current_date and o.display_policy = 'public'
order by o.sale_date, c.case_no, o.item_no
"""
SHOW_MAX = 5
_UNIT = re.compile(r"(?:\d+동\s*)?(?:지하\s*)?\d+층\s*[A-Z]?\d+호|(?:\d+동\s*)?[A-Z]?\d+호")


def unit_of(address: str | None) -> str | None:
    """주소에서 「동 · 층 · 호」만 (순수 함수)."""
    m = _UNIT.search(address or "")
    return re.sub(r"\s+", " ", m.group(0)).strip() if m else None


def same_building(item_id: str) -> dict[str, Any] | None:
    if item_id.startswith("OB-"):
        return None
    with connect() as c:
        rows = c.execute(_BUILDING_SQL, (item_id,)).fetchall()
    if not rows:
        return None
    return {
        "n": len(rows),
        "cases": len({r["case_id"] for r in rows}),
        "list": [
            {
                "item_id": r["item_id"],
                "no": r["case_no"],
                "unit": unit_of(r["address"]),
                "date": r["sale_date"],
                "min_price_krw": r["min_price_krw"],
            }
            for r in rows[:SHOW_MAX]
        ],
    }
