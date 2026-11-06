"""감정가 나눔(물건상세) → 토지·건물 금액 · 제시외 건물 · 대지권 (11/7 대표님 — 원본 없이 물건상세로 채움).

법원 물건상세에는 감정평가서 원본 없이도
1) 매각 목록마다 감정가(`gdsDspslObjctLst` · `auctnLstDvsCd` 01 토지 · 02 건물 · 03 집합건물),
2) 제시외 건물(`gdsNotSugtBldLsstAll` — 목록마다 같은 줄이 되풀이돼 옴),
3) 대지권(`rgltLandLstAll` — 땅 전체 면적 분의 우리 몫)
이 들어 있다. 이것을 손님 화면 · 분석이 읽는 모양으로 바꾼다. 순수 함수 — DB·네트워크를 쓰지 않음.
"""

import re
from typing import Any

from aucs_rules.result import RuleResult, Status

RULE_ID = "APPRAISAL-02"

LAND, BUILDING, UNIT = "01", "02", "03"
_NUM = re.compile(r"[\d,]+(?:\.\d+)?")


def _int(v: Any) -> int | None:
    try:
        n = int(float(str(v).replace(",", "")))
    except (TypeError, ValueError):
        return None
    return n if n > 0 else None


def _m2(v: Any) -> float | None:
    """「112㎡」「1,008.5㎡」 → 숫자. 없으면 None."""
    m = _NUM.search(str(v or ""))
    if not m:
        return None
    try:
        x = float(m.group(0).replace(",", ""))
    except ValueError:
        return None
    return x if x > 0 else None


def _flat(nested: Any) -> list[dict[str, Any]]:
    """[[…], […]] 또는 […] 를 한 줄로."""
    out: list[dict[str, Any]] = []
    for x in nested or []:
        if isinstance(x, list):
            out.extend(y for y in x if isinstance(y, dict))
        elif isinstance(x, dict):
            out.append(x)
    return out


def appraisal_parts(
    objects: list[dict[str, Any]] | None,
    extras: Any = None,
    land_rights: Any = None,
) -> RuleResult:
    """매각 목록 · 제시외 · 대지권 → 금액 나눔. 목록이 없으면 「모름」(빈 값)."""
    objs = [o for o in objects or [] if isinstance(o, dict)]
    if not objs:
        return RuleResult({}, Status.UNKNOWN, RULE_ID, [])
    sums = {LAND: 0, BUILDING: 0, UNIT: 0}
    seen: set[str] = set()
    for o in objs:
        code = str(o.get("auctnLstDvsCd") or "")
        amt = _int(o.get("aeeEvlAmt"))
        if code in sums and amt:
            sums[code] += amt
            seen.add(code)
    kind: str | None
    land, bldg, unit = sums[LAND] or None, sums[BUILDING] or None, sums[UNIT] or None
    if seen == {LAND}:
        kind = "land_only"  # 땅만 팔림(그 위 건물은 매각에서 빠짐)
    elif seen == {BUILDING}:
        kind = "building_only"  # 건물만 팔림(땅은 매각에서 빠짐)
    elif {LAND, BUILDING} <= seen:
        kind = "land_and_building"
    elif UNIT in seen:
        kind = "unit"  # 아파트·오피스텔처럼 한 목록(대지권 포함)
    else:
        kind = None
    pct = round(bldg * 100 / (land + bldg), 1) if land and bldg else None

    # 제시외 건물 — 목록마다 같은 줄이 되풀이돼 오므로 (목록 번호, 순번)으로 하나만
    ex: dict[tuple[Any, Any], dict[str, Any]] = {}
    for e in _flat(extras):
        key = (e.get("dspslObjctSeq"), e.get("sugtBsdsBldSeq"))
        if key in ex:
            continue
        ex[key] = {
            "use": (e.get("etcUsgCtt") or "").strip() or None,
            "area_m2": _m2(e.get("bldArDts")),
            "structure": (e.get("bldStrcDts") or "").strip() or None,
            "krw": _int(e.get("evlAmt")),
        }
    ex_list = list(ex.values())
    ex_krw = sum(x["krw"] or 0 for x in ex_list) or None

    # 대지권 — 땅 전체 면적(분모)과 우리 몫(분자). 몫은 숫자, 분모가 땅 면적과 같을 때 ㎡ 로 봄
    lr_m2 = 0.0
    lr_total = 0.0
    for r in _flat(land_rights):
        num, den = _m2(r.get("rgltRateNmrtVal")), _m2(r.get("rgltRateDnmnVal"))
        area = _m2(r.get("landArDts"))
        if num and den and area:
            lr_m2 += area * num / den
            lr_total += area
    value = {
        "kind": kind,
        "land_krw": land,
        "building_krw": bldg,
        "unit_krw": unit,
        "building_pct": pct,
        "extras": ex_list,
        "extras_krw": ex_krw,
        "land_right_m2": round(lr_m2, 2) if lr_m2 else None,
        "land_total_m2": round(lr_total, 2) if lr_total else None,
    }
    ev = [{"source": "물건상세", "lists": len(objs), "extras": len(ex_list)}]
    return RuleResult(value, Status.CONFIRMED, RULE_ID, ev)
