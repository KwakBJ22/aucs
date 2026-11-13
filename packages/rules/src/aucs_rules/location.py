"""입지(LOC-01, 11/13 대표님): 가까운 역 등급 · 주요 업무지구 · 가까운 정비사업 → 한 줄.

- 등급은 가장 가까운 역까지 직선거리: 500m 안 초역세권 · 1km 안 역세권 · 3km 안 준역세권.
- 업무지구는 역 이름으로(강남 · 여의도 · 시청 · 판교). 통근 시간은 자료가 없어 내지 않고,
  가까운 역(1km 안)과 같은 노선이면 「○호선 한 번에」만 붙임.
- 정비사업은 「구역 안」이 먼저(11/14): 토지 이용 계획 글 · 대표지번 · 단지 이름으로 가름.
  구역 밖은 대표지번까지 직선 300m 안 한 곳만 참고로(구역 경계가 아님) → 늘 「추정」.
"""

from typing import Any

from aucs_rules.result import RuleResult, Status

RULE_ID = "LOC-01"
GRADES = ((500, "초역세권"), (1000, "역세권"), (3000, "준역세권"))
HUBS = {"강남": "강남역", "여의도": "여의도역", "시청": "시청역(도심)", "판교": "판교역"}
NEAR_LINE_M = 1000  # 「한 번에」를 따질 때 내 역으로 치는 거리
ZONE_NEAR_M = 300  # 「가까운 정비사업」(구역 밖 참고)으로 치는 거리 — 대표지번까지라 넓히면 뜻이 흐려짐(11/14 대표님)
ZONE_GUESS_M = 500  # 토지 이용 계획이 「정비구역」인 물건에 어느 구역인지 이어 볼 거리
INSIDE = {"zone": "정비구역 안", "district": "재정비촉진지구 안", "planned": "정비예정구역"}
DONE_STAGES = ("준공", "청산", "해산", "입주")
SKIP_TYPES = ("지역주택",)

# 정비사업 한 줄 → ref.place_points 주소(수집기와 API 가 같은 식을 씀)
ZONE_ADDRESS_SQL = (
    "'서울특별시 ' || z.gu || ' ' || z.dong_name || ' ' || z.main_no"
    " || case when coalesce(z.sub_no, 0) > 0 then '-' || z.sub_no else '' end"
)


def zone_usable(stage: str | None, biz_type: str | None) -> bool:
    """끝난 사업(준공 · 청산 · 해산 · 입주)과 지역주택조합은 뺌 — 물건 잇기와 입지가 같이 씀."""
    s, b = stage or "", biz_type or ""
    return not any(x in s for x in DONE_STAGES) and not any(x in b for x in SKIP_TYPES)


def station_grade(straight_m: int | float | None) -> str | None:
    """가장 가까운 역까지 직선거리 → 초역세권 / 역세권 / 준역세권 / None."""
    if straight_m is None:
        return None
    return next((name for limit, name in GRADES if straight_m <= limit), None)


def _km(m: int | float) -> str:
    return f"{m:,.0f}m" if m < 1000 else f"{m / 1000:.1f}km"


def inside_zone(redev: dict[str, Any] | None, plan_zone: str | None) -> dict[str, Any] | None:
    """이 물건이 정비사업 구역 안인지(11/14 대표님 — 조합원 승계 · 가치는 「구역 안」이냐로 갈림).

    redev: 분석이 이은 구역(대표지번 · 단지 이름 · 토지 이용 계획 + 가까운 구역) · plan_zone: 토지 이용 계획 글.
    → {'kind', 'label', 'name', 'stage'} 또는 None(구역 밖이거나 아직 모름)."""
    kind = "zone" if redev else plan_zone
    if kind not in INSIDE:
        return None
    r = redev or {}
    return {"kind": kind, "label": INSIDE[kind], "name": r.get("name"), "stage": r.get("stage")}


def location(
    stations: list[dict[str, Any]],
    hubs: list[dict[str, Any]],
    zones: list[dict[str, Any]],
    inside: dict[str, Any] | None = None,
) -> RuleResult:
    """stations: [{name, lines, straight_m}] 가까운 순 · hubs: [{name, lines, straight_m}] ·
    zones: [{key, name, biz_type, stage, straight_m}] · inside: inside_zone() 결과
    → {'grade', 'hubs', 'inside', 'redev', 'line'}. 구역 안이면 「가까운 정비사업」은 내지 않음."""
    grade = station_grade(stations[0]["straight_m"]) if stations else None
    mine = {
        ln for s in stations if s["straight_m"] <= NEAR_LINE_M for ln in s.get("lines") or []
    }
    hub_out = []
    for h in sorted(hubs, key=lambda x: x["straight_m"])[:3]:
        same = sorted(mine & set(h.get("lines") or []))
        hub_out.append(
            {
                "name": HUBS.get(h["name"], h["name"]),
                "straight_m": h["straight_m"],
                "direct": same[0] if same else None,
            }
        )
    seen: set[str] = set()
    redev = []
    for z in sorted(zones, key=lambda x: x["straight_m"]):
        if z["key"] in seen or not zone_usable(z.get("stage"), z.get("biz_type")):
            continue
        seen.add(z["key"])
        redev.append({k: z.get(k) for k in ("name", "biz_type", "stage", "straight_m")})
    redev = [] if inside and inside["kind"] == "zone" else redev[:1]
    parts = []
    if stations and grade:
        s = stations[0]
        lines = f"({' · '.join(s['lines'])})" if s.get("lines") else ""
        parts.append(f"{s['name']}{lines} 직선 {_km(s['straight_m'])} {grade}")
    direct = next((h for h in hub_out if h["direct"]), None)
    if direct:
        parts.append(f"{direct['name']}까지 {direct['direct']} 한 번에")
    if inside:  # 구역 밖 「가까운 정비사업」은 한 줄에 넣지 않음(11/14)
        parts.append(inside["label"] + (f"({inside['stage']})" if inside.get("stage") else ""))
    value = {"grade": grade, "hubs": hub_out, "inside": inside, "redev": redev,
             "line": " · ".join(parts) or None}  # fmt: skip
    ev = [{"nearest_m": stations[0]["straight_m"] if stations else None, "grades": GRADES}]
    return RuleResult(value, Status.ESTIMATED, RULE_ID, ev)
