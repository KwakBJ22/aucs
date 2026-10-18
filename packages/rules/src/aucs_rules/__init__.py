"""옥스 분석 규칙. DB·네트워크·현재 시각을 직접 쓰지 않는 순수 함수만 둡니다."""

from aucs_rules.result import RuleResult, Status

ENGINE_VERSION = "rules-0.3.0"

__all__ = ["ENGINE_VERSION", "RuleResult", "Status"]
