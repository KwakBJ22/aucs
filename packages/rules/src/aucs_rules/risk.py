"""위험 신호 (04탭 6절·11절). 자료가 없어 검사 못 한 신호는 「없음」이 아니라 「모름」.

치명(fatal): 선순위 임차인 인수·유치권·법정지상권·지분 매각·대항력 있는 임차권등기 — 점수로 상쇄하지 않음.
"""

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from aucs_rules.redev_member import member_transfer
from aucs_rules.result import Status

LEVEL_ORDER = {"fatal": 0, "high": 1, "mid": 2, "low": 3, "info": 4}


@dataclass(frozen=True)
class Signal:
    rule_id: str
    level: str
    title: str
    status: Status
    evidence: list[dict[str, Any]] = field(default_factory=list)
    ftype: str | None = None  # 실패 유형 T1~T11 (아래 FAILURE_TYPES)


# 낙찰자가 실제로 손해를 본 길을 11가지로 묶은 것. 화면에는 걸린 유형만, PC 전문가 보기는 전체.
FAILURE_TYPES = {
    "T1": "선순위 임차인·전세권을 떠안음",
    "T2": "배당요구 기한을 넘긴 임차인",
    "T3": "상가 임차인 보증금 한도 초과",
    "T4": "세금이 먼저 배당됨",
    "T5": "낙찰 뒤 권리가 바뀜",
    "T6": "입찰표 금액 실수",
    "T7": "재개발·재건축 조합원 자격",
    "T8": "토지·건물 따로 · 대지권",
    "T9": "허가·자격이 필요한 물건",
    "T10": "숨은 비용(관리비·위반건축물 등)",
    "T11": "값어치·대출·자금",
}
RULE_TYPE = {
    "risk.senior_tenant": "T1", "risk.prior_rights": "T1", "risk.lease_reg": "T1",
    "risk.tenants_unknown": "T1", "risk.family": "T1",
    "risk.late_claim": "T2", "risk.commercial_over": "T3", "risk.tax_first": "T4",
    "risk.small_base_mortgage": "T5", "risk.stop": "T5", "risk.resale": "T6",
    "risk.redev_member": "T7", "risk.partial": "T8", "risk.land_right": "T8",
    "risk.superficies": "T8", "risk.share": "T8", "risk.farmland": "T9", "risk.special_corp": "T9",
    "risk.illegal": "T10", "risk.neighborhood_villa": "T10", "risk.old": "T10", "risk.lien": "T10",
    "risk.over_cost": "T11", "risk.no_loan": "T11",
    # 감정평가 요항(11/4)
    "risk.greenbelt": "T9", "risk.edu_zone": "T9", "risk.permit_exempt": "T9",
    "risk.old_appraisal": "T11", "risk.no_road": "T11", "risk.narrow_road": "T11", "risk.extra_building": "T8", "risk.doc_diff": "T10",
}  # fmt: skip


_HOUSING_WORDS = re.compile(r"(다세대|연립|다가구|단독|주택|빌라|아파트)")
_LAND_OR_HOUSE = re.compile(r"(대지|임야|잡종지|토지|단독|다가구|공장|창고|^\s*전\b|^\s*답\b)")
_COMMERCIAL = re.compile(r"(근린|상가|판매|점포)")
_SPECIAL_CONDITION = re.compile(r"(대항력\s*포기|주택도시보증공사|HUG|일괄매각|제시외)")


PRIOR_KINDS = ("전세권", "가등기", "가처분", "지상권", "지역권", "임차권", "근저당")


def prior_rights_title(texts: list[str]) -> str:
    """명세서 「소멸되지 않는 권리」 글에 실제로 나온 권리만(11/1 — 예전엔 넷을 다 늘어놓았음)."""
    t = " ".join(texts or [])
    kinds = [k for k in PRIOR_KINDS if k in t]
    return f"선순위 {'·'.join(kinds)} 인수" if kinds else "매각으로 안 지워지는 권리 인수"


def signals(f: dict[str, Any]) -> list[Signal]:
    """물건 사실(f)로 위험 신호 목록을 만듭니다. 키가 없으면 그 신호는 「모름」."""
    out: list[Signal] = []

    def add(
        rule_id: str, level: str, title: str, status: Status = Status.ESTIMATED, **ev: Any
    ) -> None:
        out.append(
            Signal(rule_id, level, title, status, [ev] if ev else [], RULE_TYPE.get(rule_id))
        )

    if f.get("senior_tenant_assumed"):
        add("risk.senior_tenant", "fatal", "선순위 임차인 보증금 인수")
    if f.get("lien_reported"):
        add("risk.lien", "fatal", "유치권 신고")
    if f.get("statutory_superficies"):
        add("risk.superficies", "fatal", "법정지상권 성립 여지")
    if f.get("is_share"):
        add("risk.share", "fatal", "지분 매각 — 공유자 우선매수")
    if f.get("lease_registration_with_power"):
        add("risk.lease_reg", "fatal", "대항력 있는 임차권등기")
    if f.get("prior_assumed_rights"):
        add(
            "risk.prior_rights",
            "high",
            prior_rights_title(f["prior_assumed_rights"]),
            rights=f["prior_assumed_rights"],
        )
    if f.get("land_or_building_only"):
        add("risk.partial", "high", "토지만 또는 건물만 매각")
    if f.get("unregistered_land_right"):
        add("risk.land_right", "mid", "대지권미등기·토지별도등기")
    if f.get("illegal_building"):
        add("risk.illegal", "mid", "위반건축물")
    if f.get("farmland_permit"):
        add("risk.farmland", "mid", "농지취득자격증명 필요")
    # ── 감정평가 요항(11/4): 토지 이용 계획 · 길
    if f.get("greenbelt"):
        add("risk.greenbelt", "mid", "개발제한구역 — 새로 짓거나 용도를 바꾸기 어려워요")
    if f.get("edu_protect") and _COMMERCIAL.search(f.get("usage_text") or ""):
        # 교육환경 보호에 관한 법률 제9조 — 보호구역 안 금지 업종(유흥·숙박 등)
        add(
            "risk.edu_zone",
            "mid",
            "교육환경보호구역 — 들일 수 없는 업종이 있어요",
            Status.NEEDS_CHECK,
        )
    if f.get("land_permit_area"):
        # 부동산 거래신고 등에 관한 법률 제14조, 시행령 제11조 — 민사집행법에 따른 경매는 허가 예외
        add(
            "risk.permit_exempt", "info", "토지거래허가구역 — 경매로 사면 허가·실거주 의무가 없어요"
        )
    if f.get("no_road") == "yes":
        add("risk.no_road", "high", "맹지 — 길에 닿지 않아 집을 짓기 어려워요")
    elif f.get("no_road") == "check":
        add("risk.no_road", "mid", "지적도에는 맹지 — 실제로 드나드는 길 확인", Status.NEEDS_CHECK)
    if f.get("narrow_road") and _LAND_OR_HOUSE.search(f.get("usage_text") or ""):
        # 건축법 제2조 제1항 제11호(도로 너비 4m) · 제44조(대지는 도로에 2m 이상 접해야)
        add("risk.narrow_road", "mid", "앞길이 4m보다 좁아요 — 새로 짓기 어려울 수 있어요",
            road_m=f.get("road_max_m"))  # fmt: skip
    if f.get("extra_building_text"):
        add(
            "risk.extra_building",
            "mid",
            "제시외 건물이 있어요 — 매각에 들어가는지 확인",
            Status.NEEDS_CHECK,
        )
    if f.get("doc_diff_text"):
        add(
            "risk.doc_diff",
            "mid",
            "감정평가서에 서류와 실제가 다른 점이 있어요",
            Status.NEEDS_CHECK,
        )
    if f.get("family_tenant"):
        add("risk.family", "mid", "가족 임차인 의심 — 실제 임대차 확인")
    if f.get("claim_after_deadline"):
        add("risk.late_claim", "mid", "배당요구종기 뒤 권리신고")
    if f.get("rehab_or_bankrupt"):
        add("risk.rehab", "mid", "회생·파산 — 정지 가능")
    if f.get("stop_attempts"):
        add("risk.stop", "mid", "정지·연기 신청 — 기일이 바뀔 수 있음")
    if f.get("resale"):
        add("risk.resale", "mid", "재매각 — 보증금 비율 확인")
    if f.get("creditor_changed"):
        add("risk.npl", "info", "채권자 바뀜")
    if f.get("claim_much_smaller_than_min"):
        add("risk.withdraw", "info", "취하 가능성")
    if f.get("documents_conflict"):
        add("risk.conflict", "high", "자료가 서로 다름", Status.NEEDS_CHECK)

    usage_code, usage_text = f.get("usage_code"), f.get("usage_text") or ""
    # 건축물대장(그 층 용도)이 있으면 그것으로, 없으면 용도 코드로 짐작(10/27)
    villa = f.get("villa_by_register")
    if villa == "confirmed":
        add(
            "risk.neighborhood_villa", "high",
            "근생빌라 — 건축물대장에 이 층이 근린생활시설이에요(주택 대출·세금 확인)",
            Status.CONFIRMED, floor_uses=f.get("floor_uses"),
        )  # fmt: skip
    elif villa == "mixed":
        add(
            "risk.neighborhood_villa", "mid",
            "이 층에 근린생활시설이 섞여 있어요 — 이 호의 용도 확인",
            Status.NEEDS_CHECK, floor_uses=f.get("floor_uses"),
        )  # fmt: skip
    elif villa != "clear" and usage_code == "21101" and _HOUSING_WORDS.search(usage_text):
        add("risk.neighborhood_villa", "mid", "근생빌라 의심 — 대출·위반건축물·세금 확인")
    note = f.get("note") or ""
    if m := _SPECIAL_CONDITION.search(note):
        add(
            "risk.special_condition",
            "high",
            "비고의 매각 조건 — 원문 확인",
            Status.NEEDS_CHECK,
            word=m.group(1),
        )
    if (approved := f.get("use_approval_date")) and (as_of := f.get("as_of")):
        if isinstance(approved, date) and (as_of - approved).days >= 365 * 30:
            add("risk.old", "mid", "사용승인 30년 이상 — 수선비·재건축 확인")
    # 감정가 저평가: 감정 1년 이상 지났고 감정가 < 실거래 시세 95% (경쟁이 붙어 낙찰가율이 높게 나옴)
    if (app := f.get("appraisal_krw")) and (mkt := f.get("market_price_krw")) and app < mkt * 0.95:
        ad, as_of0 = f.get("appraisal_date"), f.get("as_of")
        old = isinstance(ad, date) and isinstance(as_of0, date) and (as_of0 - ad).days >= 365
        if old or ad is None:
            add(
                "risk.low_appraisal", "info", "감정가가 시세보다 낮아요 — 더 높게 팔릴 수 있어요",
                Status.ESTIMATED if old else Status.NEEDS_CHECK, ratio=round(app / mkt, 3),
            )  # fmt: skip
    # 오래된 감정(11/4): 가격시점에서 1년 넘게 지났으면 알림 — 저평가 신호가 이미 나왔으면 되풀이하지 않음
    ad1, as1 = f.get("appraisal_date"), f.get("as_of")
    if isinstance(ad1, date) and isinstance(as1, date) and (as1 - ad1).days >= 365:
        if not any(s.rule_id == "risk.low_appraisal" for s in out):
            years = (as1 - ad1).days // 365
            add("risk.old_appraisal", "info", f"감정한 지 {years}년 넘었어요 — 지금 값과 다를 수 있어요",
                Status.CONFIRMED, appraisal_date=str(ad1))  # fmt: skip
    if f.get("commercial_over_limit"):
        add(
            "risk.commercial_over",
            "high",
            "상가 임차인 보증금이 보호 한도를 넘어요 — 떠안을 수 있어요",
        )
    if tb := f.get("tax_before_tenant"):  # "high"/"mid" — 법정기일 확인 전까지 세금이 먼저라고 봄(11/11)
        add(
            "risk.tax_first",
            tb if tb in ("high", "mid") else "high",
            "세금이 임차인보다 먼저일 수 있어요 — 세금 법정기일을 확인하기 전엔 모자란 보증금을 떠안는다고 보세요",
            Status.NEEDS_CHECK,
        )
    if f.get("small_base_mortgage") and f.get("junior_tenant"):
        add(
            "risk.small_base_mortgage", "high",
            "말소기준 근저당이 작아요 — 낙찰 뒤 갚아 없어지면 임차인을 떠안을 수 있어요",
            Status.NEEDS_CHECK,
        )  # fmt: skip
    if z := f.get("in_redev_zone"):
        kind = ""
        if isinstance(z, dict):
            kind = "(" + " · ".join(x for x in (z.get("biz_type"), z.get("stage")) if x) + ")"
        # 규제지역이면 낙찰자가 조합원이 되는지까지(REDEV-01, 11/13) — 아니거나 모르면 예전 한 줄
        m = (
            member_transfer(z.get("biz_type"), z.get("stage"), f.get("regulated_area"))
            if isinstance(z, dict)
            else None
        )
        if m and m.value:
            add(
                "risk.redev_member",
                "high" if m.value["blocked"] else "mid",
                m.value["title"],
                m.status,
                zone=z,
                member=m.value,
            )
        else:
            add(
                "risk.redev_member",
                "mid",
                f"정비사업 구역{kind} — 조합원 자격·현금청산 확인",
                Status.NEEDS_CHECK,
                **({"zone": z} if isinstance(z, dict) else {}),
            )
    if f.get("special_corp_owner"):
        add("risk.special_corp", "high", "학교·복지·의료법인 소유 — 허가서 없으면 보증금 몰수")
    if f.get("assumed_krw"):
        add("risk.no_loan", "mid", "떠안는 돈이 있어 대출이 어려워요 — 전액 현금 확인")
    if (cost := f.get("total_cost_krw")) and (mkt := f.get("market_price_krw")) and cost > mkt:
        add("risk.over_cost", "high", "총투입이 추정 시세보다 큼", gap_krw=cost - mkt)

    if "tenants_checked" in f and not f["tenants_checked"]:
        add(
            "risk.tenants_unknown",
            "info",
            "임차인 자료 미확인 — 안전으로 보지 않음",
            Status.UNKNOWN,
        )
    return sorted(out, key=lambda s: LEVEL_ORDER[s.level])


def top_signal(sig: list[Signal]) -> Signal | None:
    """카드 신호등: 가장 높은 등급 하나."""
    return sig[0] if sig else None
