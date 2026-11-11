"""역까지 걸어서(WALK-01, 11/12 대표님): 직선거리로 도보 거리 · 시간을 어림.

네이버 길찾기 API 는 자동차만 줘서 실제 도보 길은 못 받음 → 직선 × 1.3(실제 길은 돌아감), 분당 67m(시속 4km).
큰길·하천·철길로 돌아가는 곳은 짧게 나올 수 있어 늘 「추정」 — 화면에 「약」을 붙이고, 정확한 길은 네이버 지도 앱으로.
"""

import math

from aucs_rules.result import RuleResult, Status

RULE_ID = "WALK-01"
DETOUR = 1.3  # 실제 걷는 길 ÷ 직선
M_PER_MIN = 67  # 시속 4km
NEAR_MIN = 15  # 목록·지도 카드에 「역 가까움」을 붙이는 도보 시간


def walk_estimate(straight_m: int | float | None) -> RuleResult:
    """직선거리(m) → {'walk_m': 10m 단위, 'walk_min': 올림 분}."""
    if straight_m is None or straight_m < 0:
        return RuleResult(None, Status.UNKNOWN, RULE_ID, [])
    walk = straight_m * DETOUR
    value = {"walk_m": int(round(walk, -1)), "walk_min": max(1, math.ceil(walk / M_PER_MIN))}
    ev = [{"straight_m": straight_m, "detour": DETOUR, "m_per_min": M_PER_MIN}]
    return RuleResult(value, Status.ESTIMATED, RULE_ID, ev)


def station_name(name: str) -> str:
    """역 기준표 이름(「오리」) → 손님이 부르는 이름(「오리역」). 이미 「역」으로 끝나면 그대로(11/12 대표님)."""
    return name if name.endswith("역") else f"{name}역"
