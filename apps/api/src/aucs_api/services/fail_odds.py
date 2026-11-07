"""최근 6개월 회차별 실제 유찰 기록 모음(WAIT-01 의 통계) — 홈 추천·모아 보기·물건 상세가 같이 씀(11/7)."""

from datetime import date, timedelta
from typing import Any

from aucs_rules.pick import usage_kind
from aucs_rules.wait import ALL, LOOKBACK_DAYS, Stats, fail_odds, round_bucket

from aucs_api.cache import memo
from aucs_api.db import connect


@memo(ttl=3600, size=4)
def fail_stats(today: date) -> Stats:
    """{(법원 코드, 종류, 회차): (유찰 수, 전체 수)} — 입찰이 열려 유찰·매각으로 끝난 회차만."""
    with connect() as c:
        rows = c.execute(
            """select c.court_code, i.usage_name, least(coalesce(r.failed_count, 0), 3) as fc,
                      count(*) filter (where r.result = 'failed') as f, count(*) as n
               from core.rounds r join core.items i using (item_id) join core.cases c using (case_id)
               where r.sale_date >= %s and r.sale_date < %s and r.result in ('failed', 'sold')
               group by 1, 2, 3""",
            (today - timedelta(days=LOOKBACK_DAYS), today),
        ).fetchall()
    out: Stats = {}
    for x in rows:
        kind, fc = usage_kind(x["usage_name"]), int(x["fc"])
        for k in ((x["court_code"], kind, fc), (ALL, kind, fc)):  # 법원별 + 모든 법원 합
            f, n = out.get(k, (0, 0))
            out[k] = (f + int(x["f"]), n + int(x["n"]))
    return out


def odds_for(r: dict[str, Any], today: date) -> dict[str, Any] | None:
    """물건 한 줄(court_code·usage_name·failed_count) → 유찰 비율, 표본이 모자라면 None."""
    v: dict[str, Any] | None = fail_odds(
        fail_stats(today),
        r["court_code"],
        usage_kind(r["usage_name"]),
        round_bucket(r["failed_count"]),
    ).value
    return v
