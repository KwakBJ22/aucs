"""물건 주변 — 상가 주변 가게(소상공인 상권정보) · 같은 동 땅 거래(국토부 토지 실거래), 11/16. 보기용(입찰가 셈에 안 씀)."""

from collections import Counter
from datetime import date, timedelta
from statistics import median
from typing import Any

# 법원 용도 → 실거래 지목(토지 실거래 jimok 칸)
JIMOK = {"대지": ["대"], "전답": ["전", "답"], "임야": ["임야"]}
MIN_TRADES = 5


def nearby_stores(row: dict[str, Any] | None) -> dict[str, Any] | None:
    """core.item_stores 한 줄 → 화면용. 못 받았거나 가게가 없으면 None."""
    if not row or not row.get("total"):
        return None
    large = sorted((row.get("by_large") or {}).items(), key=lambda x: -x[1])
    same = row.get("same_list") or []
    first = Counter(
        str(s.get("small") or s.get("large") or "").strip()
        for s in same
        if str(s.get("floor") or "") == "1" and (s.get("small") or s.get("large"))
    )
    as_of = row.get("as_of")
    return {
        "radius_m": row.get("radius_m") or 300,
        "total": int(row["total"]),
        "top": [[k, int(v)] for k, v in large[:3]],
        "same_parcel": int(row.get("same_parcel") or 0),
        "ground": [k for k, _ in first.most_common(3)],  # 같은 건물 1층 업종
        "as_of": as_of.isoformat() if isinstance(as_of, date) else as_of,
    }


def land_trade_price(
    usage: str | None, zones: list[str] | None, trades: list[dict[str, Any]], today: date
) -> dict[str, Any] | None:
    """같은 동(읍면동) · 같은 지목 땅 거래 2년의 ㎡당 가운데값. 지분 거래는 뺌.

    같은 용도지역 거래가 5건 넘으면 그것만, 아니면 지목만 맞춤. 5건이 안 되면 None.
    trades: {"deal_date", "price_krw", "land_area_m2", "sub_type"(「지목|용도지역」), "contract_kind"}
    """
    jimoks = JIMOK.get((usage or "").strip())
    if not jimoks:
        return None
    since = today - timedelta(days=730)
    rows = []
    for t in trades:
        jm, _, use = str(t.get("sub_type") or "").partition("|")
        area, price = t.get("land_area_m2"), t.get("price_krw")
        if jm not in jimoks or t.get("contract_kind") == "지분" or not area or not price:
            continue
        if t.get("deal_date") and t["deal_date"] < since:
            continue
        rows.append((float(price) / float(area), use))
    zs = [z for z in (zones or []) if z]
    same_zone = [p for p, u in rows if u and any(u in z or z in u for z in zs)]
    pick, basis = (
        (same_zone, "zone") if len(same_zone) >= MIN_TRADES else ([p for p, _ in rows], "jimok")
    )
    if len(pick) < MIN_TRADES:
        return None
    return {
        "per_m2_krw": int(round(median(pick), -3)),
        "n": len(pick),
        "basis": basis,
        "jimok": "·".join(jimoks),
        "zone": zs[0] if basis == "zone" else None,
    }
