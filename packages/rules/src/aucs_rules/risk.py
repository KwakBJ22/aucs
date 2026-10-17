"""위험 신호 (04탭 6절·11절). 자료가 없어 검사 못 한 신호는 「없음」이 아니라 「모름」.

치명(fatal): 선순위 임차인 인수·유치권·법정지상권·지분 매각·대항력 있는 임차권등기 — 점수로 상쇄하지 않음.
"""

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from aucs_rules.result import Status

LEVEL_ORDER = {"fatal": 0, "high": 1, "mid": 2, "low": 3, "info": 4}


@dataclass(frozen=True)
class Signal:
    rule_id: str
    level: str
    title: str
    status: Status
    evidence: list[dict[str, Any]] = field(default_factory=list)


_HOUSING_WORDS = re.compile(r"(다세대|연립|다가구|단독|주택|빌라|아파트)")
_SPECIAL_CONDITION = re.compile(r"(대항력\s*포기|주택도시보증공사|HUG|일괄매각|제시외)")


def signals(f: dict[str, Any]) -> list[Signal]:
    """물건 사실(f)로 위험 신호 목록을 만듭니다. 키가 없으면 그 신호는 「모름」."""
    out: list[Signal] = []

    def add(
        rule_id: str, level: str, title: str, status: Status = Status.ESTIMATED, **ev: Any
    ) -> None:
        out.append(Signal(rule_id, level, title, status, [ev] if ev else []))

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
            "선순위 전세권·가등기·가처분·지상권 인수",
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
    if usage_code == "21101" and _HOUSING_WORDS.search(usage_text):
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
    if (app := f.get("appraisal_krw")) and (mkt := f.get("market_price_krw")) and app < mkt * 0.9:
        add("risk.low_appraisal", "info", "감정가가 추정 시세보다 낮음 — 교차 확인")
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
