"""건축물대장(표제부·층별개요) → 화면과 위험 신호가 쓰는 요약 (순수 함수).

- 지번: 법원 물건의 lot_no 「508-123」·「산12-3」·「1-2^3-4」(여러 필지면 첫 필지) → (대지구분, 번, 지)
- 동·층: 주소 「304동 2층203호」·「제4층 제401호」에서 읽음. 아파트처럼 동이 여러 개면 그 동의 표제부를 고름.
- 근생빌라: 주택으로 나온 물건인데 그 층의 용도가 근린생활시설뿐이면 confirmed, 섞여 있으면 mixed,
  주택뿐이면 clear(용도 코드로 짐작한 의심을 내림).
"""

import re
from datetime import date
from typing import Any

HOUSING = re.compile(r"(다세대|연립|다가구|단독|주택|빌라|아파트)")
NEIGHBORHOOD = re.compile(r"근린생활")


def parse_jibun(lot_no: str | None) -> tuple[str, str, str] | None:
    """'508-123' → ('0', '0508', '0123') · '산12-3' → ('1', '0012', '0003') · 여러 필지는 첫 것."""
    for part in (lot_no or "").replace(" ", "").split("^"):
        m = re.fullmatch(r"(산)?(\d{1,4})(?:-(\d{1,4}))?", part)
        if m:
            return (
                "1" if m.group(1) else "0",
                f"{int(m.group(2)):04d}",
                f"{int(m.group(3) or 0):04d}",
            )
    return None


def lot_key(plat: str, bun: str, ji: str) -> str:
    """건축물대장 표의 지번 키: 「0100-0002」, 산이면 「산0100-0002」 (수집·분석이 같이 씀)."""
    return f"{'산' if plat == '1' else ''}{bun}-{ji}"


# 「304동 2층」·「가동 지하1층」만 동으로 봄(「신당동 217」 같은 동네 이름은 앞 글자가 한글이라 뺌)
_DONG = re.compile(
    r"(?<![가-힣\d])제?\s*(\d{1,4}|[가-하A-Z])\s*동\s*(?=제?\s*(?:지하|지층|지)?\s*\d+\s*(?:층|호))"
)
_FLOOR = re.compile(r"(지하)?\s*제?\s*(\d{1,3})\s*층")


_LETTER = {"에이": "A", "비": "B", "씨": "C", "디": "D", "이": "E"}


def _norm_dong(a: str) -> str:
    """「주건축물제1동」→「제1동」, 「에이동」→「A동」 — 대장·공시가격에 흔한 꼴도 동으로 읽게(11/11)."""
    a = re.sub(r"주건축물\s*", " ", a)
    return re.sub(
        r"(?<![가-힣])(에이|비|씨|디|이)(?=\s*동)", lambda m: " " + _LETTER[m.group(1)], a
    )


def dong_key(v: Any) -> str:
    """동 이름 비교용 열쇠: 「제304동」·「304동」·「주건축물제2동」 → 「304」·「2」, 「에이동」·「A동」 → 「A」."""
    s = _norm_dong(str(v or ""))
    s = re.sub(r"(제|동|\s)", "", s)
    s = _LETTER.get(s, s).upper()
    d = re.sub(r"\D", "", s)
    return d.lstrip("0") or d if d else s


def unit_from_address(address: str | None) -> dict[str, Any]:
    """주소 → {'dong': '304' | None, 'floor': 2 | -1(지하1) | None}."""
    a = _norm_dong(address or "")
    d = _DONG.search(a)
    f = _FLOOR.search(a)
    floor = None
    if f:
        floor = -int(f.group(2)) if f.group(1) else int(f.group(2))
    return {"dong": d.group(1) if d else None, "floor": floor}


_HO = re.compile(r"(?:제\s*)?((?:지하?|B|비)?\s*\d{1,5})\s*호")


def ho_from_address(address: str | None) -> str | None:
    """「제7층 제701호」 → 「701」, 「지하1층 비01호」 → 「비01」. 마지막 「…호」를 씀."""
    hits = _HO.findall(address or "")
    return re.sub(r"\s", "", hits[-1]) if hits else None


def same_unit(a: str | None, b: str | None) -> bool:
    """두 주소가 같은 집(같은 지번 안)인지: 호수가 둘 다 있으면 동·호수가 같아야, 둘 다 없으면 같은 집으로 봄.
    한쪽만 호수가 있으면 모름 → 잇지 않음(아파트는 한 지번에 수백 집이라 함부로 잇지 않음, 10/28)."""
    ha, hb = ho_from_address(a), ho_from_address(b)
    if (ha is None) != (hb is None):
        return False
    if ha is not None and ha.lstrip("0") != (hb or "").lstrip("0"):
        return False
    da, db = unit_from_address(a)["dong"], unit_from_address(b)["dong"]
    return not (da and db and _key(da) != _key(db))


def _key(s: Any) -> str:
    """동 이름 비교용: 「제304동」·「304동」·「304」 → 「304」."""
    return re.sub(r"(제|동|\s)", "", str(s or ""))


def _int(v: Any) -> int | None:
    try:
        return int(float(str(v).strip()))
    except (TypeError, ValueError):
        return None


def _float(v: Any) -> float | None:
    try:
        x = float(str(v).strip())
        return x if x > 0 else None
    except (TypeError, ValueError):
        return None


def _date(v: Any) -> date | None:
    s = re.sub(r"\D", "", str(v or ""))
    if len(s) != 8:
        return None
    try:
        return date(int(s[:4]), int(s[4:6]), int(s[6:]))
    except ValueError:
        return None


def pick_title(titles: list[dict[str, Any]], dong: str | None) -> dict[str, Any] | None:
    """여러 동 가운데 이 물건의 표제부. 동이 맞는 것 → 주건축물 중 연면적이 가장 큰 것."""
    if not titles:
        return None
    if dong:
        same = [t for t in titles if _key(t.get("dongNm")) == _key(dong)]
        if same:
            return same[0]
    main = [t for t in titles if str(t.get("mainAtchGbCd", "0")) == "0"] or titles
    return max(main, key=lambda t: _float(t.get("totArea")) or 0)


def floor_uses(floors: list[dict[str, Any]], floor: int | None, dong: str | None) -> list[str]:
    """그 층(동이 있으면 그 동)의 용도들. 층을 모르면 빈 목록."""
    if floor is None:
        return []
    out = []
    for r in floors:
        if dong and r.get("dongNm") and _key(r.get("dongNm")) != _key(dong):
            continue
        under = "지하" in str(r.get("flrGbCdNm") or "")
        no = _int(r.get("flrNo"))
        if no is None or (-no if under else no) != floor:
            continue
        use = " ".join(x for x in [r.get("mainPurpsCdNm"), r.get("etcPurps")] if x).strip()
        if use and use not in out:
            out.append(use)
    return out


def summarize(
    titles: list[dict[str, Any]],
    floors: list[dict[str, Any]],
    address: str | None,
    usage_text: str | None,
    as_of: date,
) -> dict[str, Any] | None:
    """화면·규칙용 요약. 표제부가 없으면 None(→ 「건축물대장 못 받음」)."""
    unit = unit_from_address(address)
    t = pick_title(titles, unit["dong"])
    if not t:
        return None
    approved = _date(t.get("useAprDay"))
    elev = (_int(t.get("rideUseElvtCnt")) or 0) + (_int(t.get("emgenUseElvtCnt")) or 0)
    park = sum(
        _int(t.get(k)) or 0
        for k in ("indrAutoUtcnt", "oudrAutoUtcnt", "indrMechUtcnt", "oudrMechUtcnt")
    )
    uses = floor_uses(floors, unit["floor"], unit["dong"])
    villa = None  # 주택으로 나온 물건만 판단
    if HOUSING.search(usage_text or "") and uses:
        nb = [u for u in uses if NEIGHBORHOOD.search(u)]
        if nb and len(nb) == len(uses) and not any(HOUSING.search(u) for u in uses):
            villa = "confirmed"
        elif nb:
            villa = "mixed"
        else:
            villa = "clear"  # 그 층은 주택 → 용도 코드로 짐작한 근생 의심은 내림
    main_use = " ".join(x for x in [t.get("mainPurpsCdNm"), t.get("etcPurps")] if x).strip() or None
    return {
        "name": (t.get("bldNm") or "").strip() or None,
        "dong": (t.get("dongNm") or "").strip() or None,
        "main_use": main_use,
        "structure": t.get("strctCdNm") or None,
        "floors_above": _int(t.get("grndFlrCnt")),
        "floors_below": _int(t.get("ugrndFlrCnt")),
        "households": _int(t.get("hhldCnt")) or None,
        "elevators": elev or None,
        "parking": park or None,
        "total_area_m2": _float(t.get("totArea")),
        "approved": approved.isoformat() if approved else None,
        "age_years": (as_of.year - approved.year) if approved else None,
        "unit_floor": unit["floor"],
        "unit_floor_uses": uses,
        "villa": villa,
        "buildings": len(titles),
    }
