"""추천 점수(PICK-01, 11/4 대표님): 「오늘의 추천」·「다음 달 더 싸지는 물건」을 고르는 100점.

싸게 살 여지 35 · 안전 25 · 내 목적 20 · 경쟁이 덜함 10 · 때 10.
치명 신호가 있거나 지분·특수매각(투자 목적이 아니면)은 추천에서 뺌(excluded).
입력은 분석 결과(시세 market · 예상 낙찰가율 sale_rate · 같은 법원 court_cell · 신호 signals …)와 물건 칸.
현재 시각은 쓰지 않음 — 남은 날(d_day)에 따른 점수는 부르는 쪽이 더함(timing_by_days).
"""

from dataclasses import dataclass
from typing import Any

from aucs_rules.result import RuleResult, Status

RULE_ID = "PICK-01"
PURPOSES = ("live", "rent", "invest")


@dataclass(frozen=True)
class PickInput:
    usage: str | None
    appraisal_krw: int | None
    min_price_krw: int | None
    failed_count: int | None
    area_m2: float | None
    is_share: bool
    is_special: bool
    analysis: dict[str, Any]


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def _won_short(n: int) -> str:
    """금액을 「8천만 원」「1억 2천만 원」처럼 짧게(이유 한 줄용)."""
    eok, man = divmod(round(n / 10_000_000), 10)  # 천만 원 단위로 반올림
    if eok and man:
        return f"{eok}억 {man}천만 원"
    if eok:
        return f"{eok}억 원"
    return f"{man}천만 원" if man else f"{round(n / 10_000):,}만 원"


def _kind(usage: str | None) -> str:
    u = usage or ""
    if "아파트" in u:
        return "apt"
    if any(
        k in u for k in ("근린", "상가", "판매")
    ):  # 「상가,오피스텔,근린시설」 묶음은 상가로(11/4 — 오피스텔로 잘못 높게 쳤음)
        return "shop"
    if "오피스텔" in u:
        return "officetel"
    if any(k in u for k in ("다세대", "연립", "빌라")):
        return "villa"
    if any(k in u for k in ("단독", "다가구")):
        return "house"
    if any(k in u for k in ("근린", "상가", "업무", "판매", "사무")):
        return "shop"
    return "land" if any(k in u for k in ("대지", "임야", "전", "답", "토지")) else "etc"


def pick_score(x: PickInput, purpose: str | None = None) -> RuleResult:
    """물건 하나의 추천 점수(0~100)와 이유. value = {score, excluded, reasons, parts}."""
    a = x.analysis or {}
    app, mn = x.appraisal_krw or 0, x.min_price_krw or 0
    signals = [s for s in (a.get("signals") or []) if isinstance(s, dict)]
    reasons: list[str] = []
    excluded: str | None = None

    # ── 걸러내기
    if any(s.get("level") == "fatal" and s.get("status") != "없음" for s in signals):
        excluded = "치명 신호"
    elif (x.is_share or x.is_special) and purpose != "invest":
        excluded = "지분·특수매각"
    elif not app or not mn:
        excluded = "금액 모름"

    # ── 싸게 살 여지(35): 예상 낙찰가(감정가 × 중앙 낙찰가율, 최저가보다 낮을 수 없음) vs 시세
    sr = a.get("sale_rate") or {}
    expect = max(mn, round(app * float(sr["p50"]) / 100)) if sr.get("p50") and app else mn
    market = (a.get("market") or {}).get("price_krw")
    if market and expect:
        gap = market - expect
        value = 35 * _clamp(gap / market / 0.25)  # 시세보다 25% 싸면 만점
        if gap >= 10_000_000:
            reasons.append(f"시세보다 {_won_short(gap)} 낮게 살 여지")
    elif app and mn:
        value = 12 * _clamp(
            (app - mn) / app / 0.5
        )  # 시세가 없으면 감정가 대비로만 — 믿을 만하지 않아 낮게
    else:
        value = 0.0

    # ── 안전(25)
    safety = 25.0
    flagged = 0
    for s in signals:
        lv, st = s.get("level"), s.get("status")
        if st == "모름":
            safety -= 2
        elif (
            st == "확인 필요"
        ):  # 「특별매각조건 확인」처럼 읽어 봐야 아는 것 — 덜 깎고, 「위험 없음」이라고도 하지 않음
            safety -= 6 if lv == "high" else 3
            flagged += 1
        elif lv == "high":
            safety -= 10
            flagged += 1
        elif lv == "mid":
            safety -= 5
            flagged += 1
    if (a.get("tenant_count") or 0) > 0:
        safety -= 3
    safety = max(0.0, safety)
    if not flagged and safety >= 20:
        reasons.append("위험 신호 없음")

    # ── 내 목적(20) — 목적마다 따로 셈해 두고 고른 목적 것을 씀
    kind = _kind(x.usage)
    area = x.area_m2 or 0
    redev = bool(a.get("redev"))
    fc = x.failed_count or 0
    disc = (app - mn) / app if app else 0
    by_purpose = {
        "live": (12 if kind == "apt" else 7 if kind in ("officetel", "villa") else 2)
        + (8 if 40 <= area <= 110 else 3 if area else 0),
        "rent": (
            12
            if kind in ("officetel", "villa")
            else 8
            if kind == "apt"
            else 6
            if kind == "shop"
            else 3
        )
        + (8 if 0 < area <= 60 else 3),
        "invest": (10 if redev else 0) + (5 if fc >= 2 else 0) + (5 if disc >= 0.3 else 0),
    }
    fit = float(by_purpose.get(purpose or "live", by_purpose["live"]))
    if redev:
        reasons.append("재개발·재건축 구역")

    # ── 경쟁이 덜함(10): 같은 법원 비슷한 물건 낙찰가율이 낮을수록
    cc = a.get("court_cell") or {}
    comp = 10 * _clamp((110 - float(cc["p50"])) / 40) if cc.get("p50") else 5.0

    # ── 때(10 중 날짜 빼고 6): 유찰 뒤 · 새 물건
    timing = (4 if fc >= 1 else 0) + (2 if a.get("new_item") else 0)
    if fc >= 1 and app and mn:
        reasons.append(f"유찰 {fc}회 · 감정가의 {round(mn * 100 / app)}%")

    score = round(value + safety + fit + comp + timing)
    return RuleResult(
        value={
            "score": 0 if excluded else score,
            "excluded": excluded,
            "reasons": reasons[:2],
            "parts": {
                "value": round(value),
                "safety": round(safety),
                "fit": round(fit),
                "comp": round(comp),
                "timing": timing,
            },
        },  # fmt: skip
        status=Status.ESTIMATED,
        rule_id=RULE_ID,
        evidence=[{"expect_krw": expect, "market_krw": market, "court_p50": cc.get("p50")}],
    )


def timing_by_days(d_day: int | None) -> int:
    """남은 날 점수(때 10 중 4): 준비할 시간이 넉넉한 2~5주가 가장 좋음."""
    if d_day is None:
        return 0
    if 14 <= d_day <= 35:
        return 4
    if 10 <= d_day < 14 or 35 < d_day <= 45:
        return 2
    return 0


def diversify(rows: list[dict[str, Any]], n: int, per_gu: int = 2) -> list[dict[str, Any]]:
    """점수 순 목록에서 같은 단지는 1건, 같은 구는 per_gu 건까지만 골라 n 건."""
    out: list[dict[str, Any]] = []
    seen_bld: set[str] = set()
    gu_n: dict[str, int] = {}
    for r in rows:
        bld = f"{r.get('place')}|{r.get('building')}"
        gu = str(r.get("place") or "")
        if r.get("building") and bld in seen_bld:
            continue
        if gu_n.get(gu, 0) >= per_gu:
            continue
        out.append(r)
        seen_bld.add(bld)
        gu_n[gu] = gu_n.get(gu, 0) + 1
        if len(out) >= n:
            break
    return out
