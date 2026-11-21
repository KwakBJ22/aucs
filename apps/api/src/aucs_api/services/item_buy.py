"""「무엇을 사나」: 건축물대장 요약 → 화면 줄"""

import re
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
    unit, unit_label = None, None
    if b.get("unit_use"):  # 그 호의 전유 용도(11/16) — 층 용도보다 정확. 줄 이름도 「이 호」(11/17)
        ratio = f" · 전용률 {b['exclusive_pct']}%" if b.get("exclusive_pct") else ""
        unit, unit_label = f"{b['unit_use']}{ratio}", "이 호"
    elif b.get("unit_floor") is not None and b.get("unit_floor_uses"):
        f = b["unit_floor"]
        unit = f"{'지하 ' + str(-f) if f < 0 else f}층 용도: {', '.join(b['unit_floor_uses'])}"
    # 「N층 가운데 M층」(11/18): 대장 지상 층수와 이 호의 층이 맞아 보일 때만(층이 건물보다 높으면 다른 동 대장이라 안 냄)
    uf, top = b.get("unit_floor"), b.get("floors_above")
    if unit and isinstance(uf, int) and isinstance(top, int) and 0 < uf <= top:
        unit += f" · 지상 {top}층 가운데 {uf}층"
    return {
        "built": built,
        "old": bool(b.get("age_years") and b["age_years"] >= 30),
        "shape": " · ".join(x for x in [b.get("main_use"), b.get("structure"), floors] if x)
        or None,
        "extra": extra or None,
        "unit": unit,
        "unit_label": unit_label,
        "villa": b.get("villa"),
        "dong": b.get("dong"),
    }


# 건폐율 · 용적률(11/21 — 경매레이더에 있던 것): 다시 짓거나 늘려 지을 여지를 보는 값이라
# 땅 · 단독 · 다가구 · 근린 · 상가 건물에만(아파트 · 빌라 · 오피스텔은 안 냄 — 화면 간결).
RATIO_USES = re.compile(r"단독|다가구|대지|근린|상가|공장|창고|숙박|주유|전답|임야")


def ratio_line(t: dict[str, Any] | None) -> str | None:
    """표제부 한 장 → 「건폐율 N% · 용적률 M%」(값이 0 · 없으면 그 칸 뺌, 순수 함수)."""
    if not t:
        return None

    def pct(v: Any) -> str | None:
        try:
            f = float(v)
        except (TypeError, ValueError):
            return None
        return f"{f:.0f}%" if f > 0 else None

    parts = [
        f"{k} {v}"
        for k, v in [("건폐율", pct(t.get("bcRat"))), ("용적률", pct(t.get("vlRat")))]
        if v
    ]
    return " · ".join(parts) or None
