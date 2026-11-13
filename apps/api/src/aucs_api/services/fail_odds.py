"""최근 6개월 회차별 실제 유찰 기록 모음(WAIT-01 의 통계) — 홈 추천·모아 보기·물건 상세가 같이 씀(11/7)."""

from datetime import date, timedelta
from typing import Any

from aucs_rules.pick import usage_kind
from aucs_rules.wait import (
    FAIL_STATS_SQL,
    LOOKBACK_DAYS,
    Stats,
    fail_odds,
    fold_stats,
    round_bucket,
)

from aucs_api.cache import memo
from aucs_api.db import connect


@memo(ttl=3600, size=4)
def fail_stats(today: date) -> Stats:
    """{(법원 코드, 종류, 회차): (유찰 수, 전체 수)} — 조회 · 접기는 규칙 wait.py 한 곳(수집기도 같이 씀, 11/14)."""
    with connect() as c:
        rows = c.execute(FAIL_STATS_SQL, (today - timedelta(days=LOOKBACK_DAYS), today)).fetchall()
    return fold_stats(rows)


def odds_for(r: dict[str, Any], today: date) -> dict[str, Any] | None:
    """물건 한 줄(court_code·usage_name·failed_count) → 유찰 비율, 표본이 모자라면 None."""
    v: dict[str, Any] | None = fail_odds(
        fail_stats(today),
        r["court_code"],
        usage_kind(r["usage_name"]),
        round_bucket(r["failed_count"]),
    ).value
    return v
