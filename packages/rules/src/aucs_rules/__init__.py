"""옥스 분석 규칙. DB·네트워크·현재 시각을 직접 쓰지 않는 순수 함수만 둡니다."""

from aucs_rules.result import RuleResult, Status

ENGINE_VERSION = "rules-0.5.0"  # 0.5.0: 낙찰가율 표본에서 유찰 횟수를 통째로 빼지 않음(11/8)
# 0.4.0: 건축물대장(사용승인·그 층 용도로 근생빌라 확정, 10/27)

__all__ = ["ENGINE_VERSION", "RuleResult", "Status"]
