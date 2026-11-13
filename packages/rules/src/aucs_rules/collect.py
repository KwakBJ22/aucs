"""모아 보기(COLLECT-01, 11/7 대표님 — 「차별화 · 손님에게 쓸모 있는 것만」).

물건 하나가 어느 모음에 드는지와 이유 한 줄, 늘어놓을 순서(sort, 클수록 앞). 분석 결과와 물건 칸만 받음.
  cheap   시세보다 싸게 살 여지 — 예상 낙찰가(PICK-01 과 같은 셈)가 실거래 시세보다 10% 넘게·1천만 원 넘게 낮음
  safe    떠안는 돈 없는 물건 — 위험·확인 필요·모름 신호가 하나도 없고 지분·특수매각이 아님(초보용)
  rising  감정 뒤 시세가 오른 곳 — 실거래 시세가 감정가보다 10% 넘게 높음(감정이 지금 값보다 낮게 잡힘)
  station 역 가까운 곳 — 역까지 직선 500m 안(거리는 부르는 쪽이 셈)
  special 특수 권리 물건 — 높음·치명 신호가 있는 물건, 무엇이 문제인지 한 줄(경험자용)
「기다리면 더 싸질 물건(next)」은 실제 유찰 비율(WAIT-01)로 서비스에서 붙임.
치명 신호가 있는 물건은 cheap·rising·station 에 넣지 않음(싸 보여도 떠안는 돈이 클 수 있음).
"""

from dataclasses import dataclass
from typing import Any

from aucs_rules.pick import _won_short, assumes_debt, expected_price, overvalued
from aucs_rules.result import RuleResult, Status
from aucs_rules.walk import station_name, walk_estimate

RULE_ID = "COLLECT-01"
KEYS = ("cheap", "safe", "rising", "next", "station", "special")
STATION_M = 500


@dataclass(frozen=True)
class CollectInput:
    appraisal_krw: int | None
    min_price_krw: int | None
    is_share: bool
    is_special: bool
    analysis: dict[str, Any]
    station: tuple[str, int] | None = None  # (역 이름, 직선 거리 m)
    failed_count: int | None = None


def collect(x: CollectInput) -> RuleResult:
    """value = {모음 키: {"reason": 이유 한 줄, "sort": 순서 값}} — 들지 않는 모음은 없음."""
    a = x.analysis or {}
    app, mn = x.appraisal_krw or 0, x.min_price_krw or 0
    signals = [s for s in (a.get("signals") or []) if isinstance(s, dict)]
    live = [s for s in signals if s.get("status") not in ("없음", "모름")]
    fatal = any(s.get("level") == "fatal" for s in live)
    debt = assumes_debt(signals)  # 떠안는 돈이 있으면 「싸다」·「시세 올랐다」가 맞지 않음(11/9)
    out: dict[str, dict[str, Any]] = {}
    if not app or not mn:
        return RuleResult(out, Status.UNKNOWN, RULE_ID, [{"note": "금액 모름"}])

    market = (a.get("market") or {}).get("price_krw")
    expect = expected_price(app, mn, a)
    if market and not fatal and not debt:
        gap = market - expect
        if gap >= max(10_000_000, market * 0.1):
            pct = round(gap * 100 / market)  # 비율 순으로 늘어놓으므로 이유에도 비율을(11/7)
            out["cheap"] = {
                "reason": f"시세보다 {_won_short(gap)}({pct}%) 낮게 살 여지",
                "sort": gap / market,
            }
        if market > app * 1.1:
            pct = round((market - app) * 100 / app)
            out["rising"] = {"reason": f"감정가보다 지금 시세가 {pct}% 높아요", "sort": pct}

    risky = [s for s in live if s.get("level") in ("fatal", "high", "mid")]
    unknown = any(s.get("status") == "모름" for s in signals)
    if (
        not risky
        and not unknown
        and not x.is_share
        and not x.is_special
        and not overvalued(
            app, mn, x.failed_count, a
        )  # 시세 없이 많이 유찰된 물건은 초보용에서 뺌(11/9)
    ):
        tenants = a.get("tenant_count") or 0
        out["safe"] = {
            "reason": "위험 신호 없음 · 임차인 없음" if tenants == 0 else "위험 신호 없음",
            "sort": (app - mn) / app,
        }

    if x.station and x.station[1] <= STATION_M and not fatal:
        name, m = x.station
        walk = walk_estimate(m).value or {}  # 11/12: 직선 m 대신 도보 어림(WALK-01)
        out["station"] = {
            "reason": f"{station_name(name)} 도보 약 {walk.get('walk_min', '-')}분",
            "sort": -m,
        }

    hard = [s for s in live if s.get("level") in ("fatal", "high")]
    if hard or x.is_share or x.is_special:
        title = str(hard[0].get("title")) if hard else "지분·특수매각"
        out["special"] = {"reason": title, "sort": (app - mn) / app}

    return RuleResult(
        out, Status.ESTIMATED, RULE_ID, [{"expect_krw": expect, "market_krw": market}]
    )


def collect_row(r: dict[str, Any], nr: dict[str, Any], today: Any) -> dict[str, dict[str, Any]]:
    """DB 물건 한 줄 → 드는 모음들({키: {reason, sort}}). 모아 보기(그때 셈)와 수집기(미리 나눔)가 같이 부름(11/14).

    r: appraisal_krw · min_price_krw · is_share · is_special_case · analysis · failed_count · sale_date ·
    station_name · station_m(직선 500m 안 가까운 역). nr: wait.next_round 값(다음 회차 · 유찰 예상)."""
    from aucs_rules.fmt import won

    st = (r["station_name"], r["station_m"]) if r.get("station_name") else None
    got: dict[str, dict[str, Any]] = collect(
        CollectInput(
            appraisal_krw=r["appraisal_krw"], min_price_krw=r["min_price_krw"],
            is_share=bool(r["is_share"]), is_special=bool(r["is_special_case"]),
            analysis=r["analysis"] or {}, station=st, failed_count=r["failed_count"],
        )
    ).value  # fmt: skip
    d_day = (r["sale_date"] - today).days if r.get("sale_date") else 0
    if "special" not in got and nr["preview"]:
        got["next"] = {
            "reason": "이미 유찰돼 위 값으로 다음 회차가 잡혔어요 · 법원 공고 전",  # 카드 값과 같은 숫자를 또 적지 않음(11/8)
            "sort": 10**13 - d_day,  # 값이 정해진 다음 회차가 맨 앞
        }
    elif "special" not in got and nr["likely_fail"] and nr.get("next_min_krw"):
        o = nr["fail_odds"]
        got["next"] = {
            "reason": f"비슷한 물건 10건 중 {o['of10']}건 유찰 · 기다리면 {won(nr['next_min_krw'])}부터",
            "sort": o["pct"] * 1000 - d_day,  # 유찰 비율 높은 순 → 입찰일 가까운 순(11/8)
        }
    return got
