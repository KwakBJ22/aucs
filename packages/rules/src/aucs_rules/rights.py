"""권리 분석: 말소기준권리와 각 권리의 소멸/인수 판정.

근거: 민사집행법 제91조(인수주의·소제주의), 대법원 판례의 말소기준권리 법리.
개발 기준이며 출시 전 법률 전문가 검토 대상입니다.
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from aucs_rules.fix_dictionary import kind_of, normalize_purpose
from aucs_rules.result import RuleResult, Status

# 말소기준이 될 수 있는 종류
BASE_KINDS = {
    "mortgage",
    "seizure",
    "provisional_seizure",
    "security_provisional_registration",
    "auction_start",
}
# 말소기준보다 앞서면 인수되는 종류
ASSUMED_IF_PRIOR = {
    "superficies",
    "servitude",
    "injunction",
    "transfer_claim_provisional_registration",
    "jeonse",
}


@dataclass(frozen=True)
class Right:
    """등기부 권리 한 줄."""

    section: str  # 갑 / 을
    rank_no: str
    purpose: str  # 등기목적 원문 (글자 오류 가능)
    receipt_date: date | None
    receipt_no: int | None = None
    amount_krw: int | None = None
    jeonse_claimed: bool = False  # 전세권자가 배당요구·경매신청했는지
    jeonse_whole_building: bool = False
    verified: bool = False  # 원문 대조로 검증됨
    source: dict[str, Any] = field(default_factory=dict)  # 문서·쪽 등


def _key(r: Right) -> tuple[date, int]:
    return (r.receipt_date or date.max, r.receipt_no or 0)


def _kind(r: Right) -> str | None:
    return kind_of(r.purpose)


def find_base_right(rights: list[Right]) -> RuleResult:
    """말소기준권리 = 기준 종류 중 접수일(같으면 접수번호)이 가장 빠른 것."""
    candidates = []
    for r in rights:
        k = _kind(r)
        if k in BASE_KINDS or (k == "jeonse" and r.jeonse_claimed and r.jeonse_whole_building):
            candidates.append(r)
    if not candidates:
        return RuleResult(None, Status.UNKNOWN, "rights.base.none", [{"note": "기준 권리 없음"}])
    base = min(candidates, key=_key)
    if base.receipt_date is None:
        return RuleResult(
            base, Status.NEEDS_CHECK, "rights.base.no_date", [{"right": base.rank_no}]
        )
    unknown = [r for r in rights if _kind(r) is None and r.receipt_date and _key(r) < _key(base)]
    status = Status.CONFIRMED if base.verified else Status.ESTIMATED
    if unknown:
        status = Status.NEEDS_CHECK  # 앞쪽에 종류를 모르는 권리가 있으면 기준이 바뀔 수 있음
    ev = [
        {"rank_no": base.rank_no, "purpose": base.purpose, "receipt_date": str(base.receipt_date)}
    ]
    return RuleResult(base, status, "rights.base", ev)


def judge_right(r: Right, base: Right | None) -> RuleResult:
    """권리 하나의 소멸/인수 판정."""
    name = normalize_purpose(r.purpose)
    k = _kind(r)
    ev = [{"rank_no": r.rank_no, "purpose": r.purpose, "normalized": name}]
    if k is None:
        return RuleResult("확인 필요", Status.NEEDS_CHECK, "rights.kind.unknown", ev)
    if k == "ownership":
        return RuleResult("해당 없음", Status.CONFIRMED, "rights.ownership", ev)
    if base is None:
        return RuleResult("확인 필요", Status.UNKNOWN, "rights.no_base", ev)
    if r is base:
        return RuleResult("말소기준", Status.ESTIMATED, "rights.is_base", ev)
    prior = _key(r) < _key(base)
    if prior and k in ASSUMED_IF_PRIOR and not (k == "jeonse" and r.jeonse_claimed):
        return RuleResult("인수", Status.ESTIMATED, "rights.assumed_prior", ev)
    if prior and k == "lease_right":
        return RuleResult("확인 필요", Status.NEEDS_CHECK, "rights.lease_prior", ev)
    return RuleResult("소멸", Status.ESTIMATED, "rights.extinguished", ev)


def analyze(rights: list[Right]) -> dict[str, Any]:
    """말소기준과 권리별 판정을 한 번에."""
    base_res = find_base_right(rights)
    base = base_res.value
    return {
        "base": base_res,
        "rights": [(r, judge_right(r, base)) for r in sorted(rights, key=_key)],
    }
