"""모든 규칙이 돌려주는 결과 모양."""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class Status(StrEnum):
    """판정의 확실한 정도."""

    CONFIRMED = "확정"
    ESTIMATED = "추정"
    NEEDS_CHECK = "확인 필요"
    UNKNOWN = "모름"


@dataclass(frozen=True)
class RuleResult:
    """규칙 결과: 값, 확실한 정도, 근거(쓴 값·원문 위치), 규칙 번호."""

    value: Any
    status: Status
    rule_id: str
    evidence: list[dict[str, Any]] = field(default_factory=list)
