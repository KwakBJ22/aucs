"""같은 집이 법원 경매와 공매에 함께 나온 경우(core.item_links, 공매 수집 때 채움)."""

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
