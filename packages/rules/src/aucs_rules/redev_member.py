"""정비구역 물건을 낙찰받으면 조합원이 되나(REDEV-01, 11/13 대표님).

- 도시 및 주거환경정비법 제39조 제2항: 투기과열지구에서 재건축은 조합설립인가 뒤, 재개발은 관리처분계획인가 뒤에
  산 사람(경매 낙찰 포함)은 조합원이 될 수 없다 → 현금청산(제39조 제3항 · 제73조).
- 같은 법 시행령 제37조 제3항 제5호: 국가 · 지방자치단체 · 금융기관(주택법 시행령 제71조 제1호 — 은행 · 중소기업은행 ·
  상호저축은행 · 보험회사 등)에 진 빚 때문에 경매 · 공매되는 경우는 예외 → 낙찰자가 조합원이 된다.
  개인 · 일반 회사가 넣은 경매는 예외가 아니다(대법원 2022다228230 — 관리처분 뒤 강제경매 낙찰자에게 매도청구).
- 법률 제14943호 부칙 제2조: 재개발은 2018. 1. 25. 전에 사업시행계획인가를 신청한 구역이면 이 제한을 받지 않는다
  (법제처 해석). 신청일 자료가 없어 재개발은 늘 「확인 필요」.
- 채권자가 누구인지는 법원 자료에 가려져 있어 여기서 가르지 않는다 — 등기부로 확인.
- 가로주택 · 소규모재건축 · 리모델링은 다른 법이라 여기서 다루지 않는다(None).
"""

from typing import Any

from aucs_rules.result import RuleResult, Status

RULE_ID = "REDEV-01"
_REBUILD_AFTER = ("조합설립", "건축심의", "사업시행", "관리처분", "이주", "철거", "착공", "분양")
_REDEV_AFTER = ("관리처분", "이주", "철거", "착공", "분양")


def zone_kind(biz_type: str | None) -> str | None:
    """사업 구분 글 → 'rebuild'(재건축) / 'redev'(재개발) / None(다른 법)."""
    b = biz_type or ""
    if "소규모" in b or "가로주택" in b or "리모델링" in b:
        return None
    if "재건축" in b:
        return "rebuild"
    if "재개발" in b:
        return "redev"
    return None


def member_transfer(biz_type: str | None, stage: str | None, regulated: bool | None) -> RuleResult:
    """낙찰자가 조합원이 되는지: {'kind', 'blocked', 'title'}. 규제지역이 아니거나 모르면 None."""
    kind = zone_kind(biz_type)
    if not kind or not regulated or not stage:
        return RuleResult(None, Status.UNKNOWN, RULE_ID, [])
    after = _REBUILD_AFTER if kind == "rebuild" else _REDEV_AFTER
    blocked = any(s in stage for s in after)
    ev: list[dict[str, Any]] = [{"biz_type": biz_type, "stage": stage, "regulated": regulated}]
    if kind == "rebuild":
        title = (
            "재건축 조합설립 뒤 — 은행·세금 빚으로 나온 경매가 아니면 낙찰받아도 조합원이 못 돼요(현금청산)"
            if blocked
            else f"재건축 구역({stage}) — 조합설립 전이라 낙찰자도 조합원이 될 수 있어요"
        )
    else:
        title = (
            "재개발 관리처분 뒤 — 은행·세금 빚으로 나온 경매가 아니면 현금청산일 수 있어요(오래된 구역은 예외)"
            if blocked
            else f"재개발 구역({stage}) — 관리처분 전이라 낙찰자도 조합원이 될 수 있어요"
        )
    status = Status.NEEDS_CHECK if blocked else Status.ESTIMATED
    return RuleResult({"kind": kind, "blocked": blocked, "title": title}, status, RULE_ID, ev)
