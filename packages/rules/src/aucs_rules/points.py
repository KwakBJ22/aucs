"""포인트 벌기(POINT-01): 올린 서류 한 건에 포인트를 주나 · 몇 점인가 (11/12 대표님, docs/design/11-points.md).

값(점수 · 하루 한도 · 등기부 새것 기준 날수)은 기준표 ref.rule_tables 'points' 에서. 순수 함수 — DB · 현재 시각을 쓰지 않음.
"""

from typing import Any

from aucs_rules.result import RuleResult, Status

RULE_ID = "POINT-01"


def points_for(
    kind: str,
    table: dict[str, Any],
    *,
    matched: bool,
    today_count: int,
    paid_before: bool,
    days_since_last_paid: int | None,
) -> RuleResult:
    """value = {'points': n, 'why': 줄 이유 또는 안 준 까닭(none/mismatch/limit/already)}.

    matched: 올린 서류가 그 물건(등기부 주소 · 감정평가서 사건번호)과 맞음.
    today_count: 이 사람이 오늘 이 종류로 받은 건수(이번 것 빼고).
    paid_before / days_since_last_paid: 이 물건 · 이 종류로 앞서 포인트를 준 적 · 그 뒤 지난 날."""
    full = int(table.get(kind) or 0)
    cap = int((table.get("daily_max") or {}).get(kind) or 0)
    ev = [{"kind": kind, "today": today_count, "cap": cap}]

    def out(points: int, why: str) -> RuleResult:
        return RuleResult({"points": points, "why": why}, Status.CONFIRMED, RULE_ID, ev)

    if not matched:
        return out(0, "mismatch")
    if paid_before:
        fresh = int(table.get("registry_fresh_days") or 30)
        # 감정평가서는 한 번 나오면 그대로 · 등기부는 앞 것보다 이만큼 지나 새로 뗀 것만
        if kind != "registry" or days_since_last_paid is None or days_since_last_paid <= fresh:
            return out(0, "already")
    if today_count >= cap:
        return out(0, "limit")
    return out(full, "first" if not paid_before else "fresh")
