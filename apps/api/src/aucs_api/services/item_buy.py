"""「무엇을 사나」: 건축물대장 요약 → 화면 줄"""

from typing import Any


def building_lines(b: dict[str, Any] | None) -> dict[str, Any] | None:
    """건축물대장 요약 → 화면 줄(값만, 같은 설명 되풀이 없이). 못 받았으면 None."""
    if not b:
        return None
    floors = " / ".join(
        x for x in [f"지상 {b['floors_above']}층" if b.get("floors_above") else None,
                    f"지하 {b['floors_below']}층" if b.get("floors_below") else None] if x
    )  # fmt: skip
    built = f"{b['approved'][:4]}년 사용승인 · {b['age_years']}년 됨" if b.get("approved") else None
    homes = (  # 단지 식별정보가 있으면 단지 전체 세대 · 동 수(11/16), 없으면 표제부 세대
        " ".join(x for x in [f"{b['complex_units']}세대" if b.get("complex_units") else None,
                             f"{b['complex_dongs']}개 동" if (b.get("complex_dongs") or 0) > 1 else None] if x)
        if b.get("complex_units") else (f"{b['households']}세대" if b.get("households") else None)
    )  # fmt: skip
    extra = " · ".join(
        x for x in [homes,
                    f"승강기 {b['elevators']}대" if b.get("elevators") else None,
                    f"주차 {b['parking']}대" if b.get("parking") else None] if x
    )  # fmt: skip
    unit = None
    if b.get("unit_use"):  # 그 호의 전유 용도(11/16) — 층 용도보다 정확
        ratio = f" · 전용률 {b['exclusive_pct']}%" if b.get("exclusive_pct") else ""
        unit = f"이 호 용도: {b['unit_use']}{ratio}"
    elif b.get("unit_floor") is not None and b.get("unit_floor_uses"):
        f = b["unit_floor"]
        unit = f"{'지하 ' + str(-f) if f < 0 else f}층 용도: {', '.join(b['unit_floor_uses'])}"
    return {
        "built": built,
        "old": bool(b.get("age_years") and b["age_years"] >= 30),
        "shape": " · ".join(x for x in [b.get("main_use"), b.get("structure"), floors] if x)
        or None,
        "extra": extra or None,
        "unit": unit,
        "villa": b.get("villa"),
        "dong": b.get("dong"),
    }
