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


_RELEASE = re.compile(r"말소\s*동의")
# 비고에만 적힌 보증기관 확약서(11/24 서울동부 2024타경57221 — 「소멸되지 않는 권리」 칸은 비고
# 「주택도시보증공사 … 대항력은 포기하며 … 임차권등기를 말소하는 데 동의한다는 확약서가 제출됨」)
_GUARANTOR = re.compile(r"주택도시보증공사|보증공사|서울보증|HUG")
_PLEDGE = re.compile(
    r"대항력\s*[은을]?\s*포기|말소\s*하는\s*(것|데)\s*에?\s*동의|말소\s*에?\s*동의"
)
_OTHER_RIGHTS = re.compile(r"전세권|가등기|가처분|지상권|지역권|근저당|유치권")


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
    # 「주택임차권등기(다만 주택도시보증공사의 말소동의 확약서가 제출됨)」 — 보증기관이 말소에 동의해
    # 매수인이 떠안지 않음(11/17: 진행 물건 714건이 「선순위 임차권 인수」로 잘못 떴음). 임차권 말고 다른
    # 권리(전세권 · 가등기 · 가처분 · 지상권 …)가 함께 적혀 있으면 지금처럼 인수 신호를 냄
    if _has(keep) and _RELEASE.search(keep or "") and not _OTHER_RIGHTS.search(keep or ""):
        out["lease_reg_released"] = [re.sub(r"\s+", " ", keep or "")[:120]]
    elif (
        not _has(keep) and _GUARANTOR.search(remark) and _PLEDGE.search(remark) and "확약" in remark
    ):
        out["lease_reg_released"] = [re.sub(r"\s+", " ", remark)[:120]]
    elif _has(keep):
        out["prior_assumed_rights"] = [re.sub(r"\s+", " ", keep or "")[:80]]
        # 「주택임차권등기는 배당에서 전액 변제받지 않으면 잔액을 매수인이 인수」 → 대항력 있는 임차권등기
        if re.search(r"임차권\s*등기", keep or "") and re.search(
            r"인수|매수인|말소되지\s*않", keep or ""
        ):
            out["lease_registration_with_power"] = True
    return out


# ── 법원 목록 비고 · 명세서 비고 글(11/24 종류별 검증) ─────────────────────────────
# 신호 규칙(risk)에 농취증 · 재매각 · 선순위 임차인 인수 칸이 있었으나 채우는 곳이 없었고, 유치권 · 법정지상권은
# 문건 · 명세서 칸에서만 찾아 비고에만 적힌 것을 놓쳤음(진행 수도권: 농취증 240 · 유치권 19 · 법정지상권 35 ·
# 대항력 있는 임차인 인수 29). 보증기관 「대항력 포기조건 매각」은 「확약」 글이 없어 말소동의로 못 봄(312).
_N_LIEN_NO = re.compile(r"유치권[^.。\n]{0,25}(철회|취하|배제|부존재|성립\s*하지\s*않|없음)")
_N_SUP = re.compile(r"법정\s*지상권")
_N_SUP_NO = re.compile(r"법정\s*지상권[^.。\n]{0,20}(성립\s*(여지\s*)?(없|하지\s*않))")
_N_FARM = re.compile(r"농지\s*취득\s*자격\s*증명|농취증")
_N_FARM_NO = re.compile(
    r"(농지\s*취득\s*자격\s*증명|농취증)[^.。\n]{0,15}(불요|불필요|필요\s*(하지\s*)?없|미발급\s*대상)"
)
_N_RESALE = re.compile(r"재\s*매각")
_N_SENIOR = re.compile(
    r"(대항력\s*(이\s*)?있는\s*임차인|선순위\s*임차인)[^.。\n]{0,80}(인수|매수인)"
)
_N_PLEDGE_KIND = re.compile(r"확약|포기\s*조건\s*매각|포기서")


def note_facts(note: str | None, have: dict[str, Any] | None = None) -> dict[str, Any]:
    """비고 글(법원 목록 비고 + 명세서 비고) → 신호 사실. have = 이미 모은 사실(겹침 판단용)."""
    text = re.sub(r"\s+", " ", note or "")
    have = have or {}
    out: dict[str, Any] = {}
    if not text.strip():
        return out
    released = bool(have.get("lease_reg_released"))
    if (
        not released
        and not have.get("prior_assumed_rights")
        and _GUARANTOR.search(text)
        and _PLEDGE.search(text)
        and _N_PLEDGE_KIND.search(text)
    ):
        released = True
        out["lease_reg_released"] = [text[:120]]
    if _LIEN.search(text) and not _N_LIEN_NO.search(text):
        out["lien_reported"] = True
    if _N_SUP.search(text) and not _N_SUP_NO.search(text):
        out["statutory_superficies"] = True
    if _N_FARM.search(text) and not _N_FARM_NO.search(text):
        out["farmland_permit"] = True
    if _N_RESALE.search(text):
        out["resale"] = True
    if not released and _N_SENIOR.search(text):
        out["senior_tenant_assumed"] = True
    return out
