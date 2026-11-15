"""이 지역 평균(AREA-01, 11/15): 한국부동산원 R-ONE 통계에서 물건의 용도 · 지역에 맞는 줄을 고름. [참고]

- 오피스텔: 오피스텔 수익률 · 전월세전환율(시도)
- 상가 · 근린시설: 집합 상가 소득수익률(분기) · 공실률(시도)
- 아파트 · 연립다세대 · 단독다가구: 전월세전환율(시군구, 없으면 시도)
- 평균일 뿐 이 물건의 값이 아님 — 입찰가 셈에는 쓰지 않고 보기용.
"""

from typing import Any

RULE_ID = "AREA-01"
_SIDO = {"서울특별시": "서울", "경기도": "경기", "인천광역시": "인천"}
Stats = dict[str, dict[str, dict[str, Any]]]  # 통계 이름 → 지역 → {period, value, unit}


def kind_of(usage_name: str | None, building_desc: str | None) -> str | None:
    """물건 용도 → officetel / shop / apt / row / house (그 밖은 None)."""
    u, d = usage_name or "", building_desc or ""
    if "오피스텔" in u and ("상가" not in u or "오피스텔" in d):
        return "officetel"
    if "상가" in u or "근린" in u:
        return "shop"
    if "아파트" in u:
        return "apt"
    if "연립" in u or "다세대" in u or "빌라" in u:
        return "row"
    if "단독" in u or "다가구" in u:
        return "house"
    return None


def _find(
    table: dict[str, dict[str, Any]] | None, sido: str, names: list[str]
) -> tuple[str, dict[str, Any]] | None:
    """지역 줄 찾기: 시군구(「경기>수원시」 · 「서울>…>강남구」) → 없으면 시도. 다른 시도의 같은 이름은 안 집음."""
    if not table:
        return None
    for n in names:
        for region, row in table.items():
            parts = region.split(">")
            if n and parts[-1] == n and parts[0] == sido and len(parts) > 1:
                return n, row
    return (sido, table[sido]) if sido in table else None


def area_stats(usage_name: str | None, building_desc: str | None, sido: str | None, sigungu: str | None,
               stats: Stats | None) -> dict[str, Any] | None:  # fmt: skip
    """→ {'kind': 'shop', 'items': [{'label', 'value', 'unit', 'region', 'period', 'per'?}]} 또는 None(해당 없음 · 자료 없음)."""
    kind, short = kind_of(usage_name, building_desc), _SIDO.get(sido or "")
    if not kind or not short or not stats:
        return None
    gu = [x for x in (sigungu or "").split() if x]
    names = [gu[-1], gu[0]] if gu else []  # 「수원시 영통구」 → 영통구, 수원시
    want = {
        "officetel": (
            ("officetel_yield", "수익률", None),
            ("officetel_conv", "전월세전환율", None),
        ),
        "shop": (
            ("shop_yield", "집합 상가 소득수익률", "분기"),
            ("shop_vacancy", "집합 상가 공실률", None),
        ),
        "apt": (("conv_apt", "전월세전환율", None),),
        "row": (("conv_row", "전월세전환율", None),),
        "house": (("conv_house", "전월세전환율", None),),
    }[kind]
    items = []
    for key, label, per in want:
        hit = _find(stats.get(key), short, names if key.startswith("conv_") else [])
        if hit:
            region, row = hit
            it = {"label": label, "value": round(float(row["value"]), 2), "unit": row.get("unit") or "%",
                  "region": region, "period": row["period"]}  # fmt: skip
            items.append({**it, "per": per} if per else it)
    return {"kind": kind, "items": items} if items else None
