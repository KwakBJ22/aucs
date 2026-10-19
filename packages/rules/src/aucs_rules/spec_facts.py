"""매각물건명세서 칸 → 위험 신호 규칙(risk.signals)이 읽는 사실 (순수 함수).

명세서 칸: keep = 매각으로 소멸되지 않는 권리, superficies = 법정지상권 개요, remark = 비고.
「해당사항없음」「없음」은 없는 것으로 봅니다. 개발 기준이며 3단계 법률 검토 대상입니다.
"""

import re
from typing import Any

_NONE = re.compile(r"^\s*(해당\s*사항\s*없음|해당\s*없음|없음|-|\.)?\s*$")
_ILLEGAL = re.compile(r"위반\s*건축")
_LAND_RIGHT = re.compile(r"대지권\s*미등기|대지권\s*없음|토지\s*별도\s*등기|별도\s*등기")
_LIEN = re.compile(r"유치권")
_SUPERFICIES = re.compile(r"법정\s*지상권|지상권")


def _has(text: str | None) -> bool:
    return bool(text) and not _NONE.match(text or "")


def spec_facts(spec: dict[str, Any] | None) -> dict[str, Any]:
    """명세서 → {illegal_building, unregistered_land_right, lien_reported, statutory_superficies,
    prior_assumed_rights, lease_registration_with_power, spec_note}. 명세서가 없으면 빈 묶음(그 신호는 「모름」 그대로)."""
    if not spec:
        return {}
    keep, sup = spec.get("keep"), spec.get("superficies")
    remark = " ".join(x for x in (spec.get("remark"), spec.get("item_remark")) if x)
    text = " ".join(x for x in (keep, sup, remark) if x)
    out: dict[str, Any] = {"spec_note": remark}
    if _ILLEGAL.search(text):
        out["illegal_building"] = True
    if _LAND_RIGHT.search(text):
        out["unregistered_land_right"] = True
    if _LIEN.search(text):
        out["lien_reported"] = True
    if (
        _has(sup)
        and _SUPERFICIES.search(sup or "")
        and not re.search(r"성립\s*(여지\s*)?없", sup or "")
    ):
        out["statutory_superficies"] = True
    if _has(keep):
        out["prior_assumed_rights"] = [re.sub(r"\s+", " ", keep or "")[:80]]
        # 「주택임차권등기는 배당에서 전액 변제받지 않으면 잔액을 매수인이 인수」 → 대항력 있는 임차권등기
        if re.search(r"임차권\s*등기", keep or "") and re.search(
            r"인수|매수인|말소되지\s*않", keep or ""
        ):
            out["lease_registration_with_power"] = True
    return out
