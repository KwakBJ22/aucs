"""기다리면 더 싸질까(WAIT-01, 11/7 대표님).

같은 법원 · 같은 종류 · 같은 회차(유찰 0·1·2·3번 이상) 물건이 최근 6개월에 실제로 유찰된 비율.
예전 판단(팔린 물건의 낙찰가율만 보고 「곧 팔린다」)은 팔리지 않은 회차를 못 봐서 늘 비어 있었음 —
실제로는 첫 회차의 88~98%가 유찰됨(11/7 셈). 법원 안 표본이 30건 아래면 모든 법원을 합쳐 보고,
그래도 모자라면 모름. 70% 넘으면 「유찰 예상」. 손님에게는 「10건 중 9건」처럼 그대로 보여 줌.
통계(stats)는 부르는 쪽이 DB에서 모아 넣음: {(법원 코드, 종류, 회차): (유찰 수, 전체 수)} — 법원 코드 "*" 는
모든 법원 합(있으면 그대로 씀, 물건마다 다시 더하지 않게).
"""

from collections.abc import Iterable
from datetime import date
from typing import Any

from aucs_rules.pick import usage_kind
from aucs_rules.result import RuleResult, Status
from aucs_rules.sale_rate import next_round_min_price

RULE_ID = "WAIT-01"
LOOKBACK_DAYS = 180
MIN_N = 30
LIKELY_PCT = 70
ALL = "*"  # 모든 법원을 합친 줄의 법원 코드

Stats = dict[tuple[str, str, int], tuple[int, int]]


def round_bucket(failed_count: int | None) -> int:
    """회차 묶음: 유찰 0·1·2번, 3번 이상은 하나로."""
    return min(failed_count or 0, 3)


def fail_odds(stats: Stats, court: str, kind: str, failed_count: int | None) -> RuleResult:
    """value = {fail, n, pct, of10, likely, scope} 또는 None(표본 모자람)."""
    fc = round_bucket(failed_count)
    f, n = stats.get((court, kind, fc), (0, 0))
    scope = "court"
    if n < MIN_N:  # 모든 법원 합(ALL 줄이 있으면 그것, 없으면 더함)
        if (ALL, kind, fc) in stats:
            f, n = stats[(ALL, kind, fc)]
        else:
            f = sum(v[0] for (c, k, b), v in stats.items() if k == kind and b == fc and c != ALL)
            n = sum(v[1] for (c, k, b), v in stats.items() if k == kind and b == fc and c != ALL)
        scope = "all"
    if n < MIN_N:
        return RuleResult(None, Status.UNKNOWN, RULE_ID, [{"n": n, "kind": kind, "round": fc}])
    pct = round(f * 100 / n)
    value: dict[str, Any] = {
        "fail": f,
        "n": n,
        "pct": pct,
        "of10": round(pct / 10),
        "likely": pct >= LIKELY_PCT,
        "scope": scope,
    }
    return RuleResult(
        value, Status.ESTIMATED, RULE_ID, [{"court": court, "kind": kind, "round": fc}]
    )


PREVIEW = "preview"  # 유찰 뒤 기일내역으로 미리 안 다음 회차(법원 공고 전)

# 통계를 모으는 조회(값: 시작일 · 오늘) — 입찰이 열려 유찰 · 매각으로 끝난 회차만. API 와 수집기가 같이 씀(11/14)
FAIL_STATS_SQL = """
select c.court_code, i.usage_name, least(coalesce(r.failed_count, 0), 3) as fc,
       count(*) filter (where r.result = 'failed') as f, count(*) as n
from core.rounds r join core.items i using (item_id) join core.cases c using (case_id)
where r.sale_date >= %s and r.sale_date < %s and r.result in ('failed', 'sold')
group by 1, 2, 3"""


def fold_stats(rows: Iterable[dict[str, Any]]) -> Stats:
    """FAIL_STATS_SQL 줄 → {(법원 코드, 종류, 회차): (유찰 수, 전체 수)} — 법원별 + 모든 법원 합."""
    out: Stats = {}
    for x in rows:
        kind, fc = usage_kind(x["usage_name"]), int(x["fc"])
        for k in ((x["court_code"], kind, fc), (ALL, kind, fc)):
            f, n = out.get(k, (0, 0))
            out[k] = (f + int(x["f"]), n + int(x["n"]))
    return out


def next_round(
    r: dict[str, Any], stats: Stats, reduction: dict[str, Any], today: date
) -> dict[str, Any]:
    """「기다리면 더 싸질 물건」 판단 한 곳(홈 추천 · 모아 보기 · 미리 매겨 두는 추천 점수).

    r: 물건 한 줄(status_code · court_code · usage_name · failed_count · min_price_krw).
    reduction: 기준표 court_reduction_pct({법원 코드: {pct}}). 유찰 예상이면 next_min_krw 를 더함."""
    preview = r["status_code"] == PREVIEW
    odds: dict[str, Any] | None = (
        None
        if preview
        else fail_odds(
            stats, r["court_code"], usage_kind(r["usage_name"]), round_bucket(r["failed_count"])
        ).value
    )
    out: dict[str, Any] = {
        "preview": preview,
        "fail_odds": odds,
        "likely_fail": bool(odds and odds["likely"]),
    }
    if out["likely_fail"] and r["min_price_krw"]:
        red_pct = (reduction.get(r["court_code"]) or {}).get("pct")
        out["next_min_krw"] = next_round_min_price(r["min_price_krw"], red_pct).value
    return out
