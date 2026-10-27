"""같은 단지: 지난 낙찰·실거래 추이(순수 함수)와 조회 SQL"""

from datetime import date, timedelta
from typing import Any

from aucs_api.services.items import COURT_NAME

PEERS_SQL = """
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


def median(xs: list[int]) -> int | None:
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
    rm, pm = median(recent), median(prev)
    trend = {
        "recent_krw": rm, "recent_n": len(recent), "prev_krw": pm, "prev_n": len(prev),
        "change_pct": round((rm - pm) * 100 / pm, 1) if rm and pm and len(recent) >= 2 and len(prev) >= 2 else None,
        "jeonse_krw": median(jeonse), "jeonse_n": len(jeonse),
        "wolse_deposit_krw": median([t["deposit_krw"] for t in wolse]),
        "wolse_rent_krw": median([t["monthly_rent_krw"] for t in wolse]), "wolse_n": len(wolse),
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
            {"q": k, "price_krw": median(v), "n": len(v)} for k, v in sorted(quarters.items())
        ][-8:],
    }
