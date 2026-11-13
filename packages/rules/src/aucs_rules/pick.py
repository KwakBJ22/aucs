"""추천 점수(PICK-01, 11/4 대표님): 「오늘의 추천」·「다음 달 더 싸지는 물건」을 고르는 100점.

항목마다 0~1 비율을 셈하고, **목적에 따라 비중을 다르게** 곱해 더함(11/4 — 목적마다 추천이 눈에 띄게 달라지게).
  목적 모름·로그인 전: 싼 정도 40 · 안전 30 · 경쟁 15 · 때 15 (개인 목적 점수 없음 — 점수 큰 것 위주)
  실거주: 싼 정도 25 · 안전 30 · 살기 좋은 집 30 · 경쟁 5 · 때 10
  임대:   싼 정도 20 · 안전 20 · 임대 수익률 35 · 세놓기 좋은 집 10 · 경쟁 5 · 때 10
  투자:   싼 정도 45 · 안전 15 · 투자 신호 20 · 경쟁 10 · 때 10
치명 신호가 있거나 지분·특수매각(투자 목적이 아니면)은 추천에서 뺌(excluded).
입력은 분석 결과(시세 market · 예상 낙찰가율 sale_rate · 같은 법원 court_cell · 신호 signals …)와 물건 칸,
남은 날(d_day)·같은 단지 월세 가운데값(rent)은 부르는 쪽이 넣음(현재 시각을 직접 쓰지 않음).
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from aucs_rules.result import RuleResult, Status
from aucs_rules.sale_rate import adjusted_rates

RULE_ID = "PICK-01"
PURPOSES = ("live", "rent", "invest")
WEIGHTS: dict[str | None, dict[str, int]] = {
    None: {"value": 40, "safety": 30, "fit": 0, "yield": 0, "comp": 15, "timing": 15},
    "live": {"value": 25, "safety": 30, "fit": 30, "yield": 0, "comp": 5, "timing": 10},
    "rent": {"value": 20, "safety": 20, "fit": 10, "yield": 35, "comp": 5, "timing": 10},
    "invest": {"value": 45, "safety": 15, "fit": 20, "yield": 0, "comp": 10, "timing": 10},
}


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
    d_day: int | None = None
    rent: dict[str, Any] = field(
        default_factory=dict
    )  # 같은 단지 1년 월세 {monthly_krw, deposit_krw, n}


OVERVALUED_FAILS = 5  # 시세 없이 이만큼 유찰되면 추천하지 않음
OVERVALUED_RATE = 30  # 시세 없이 최저가가 감정가의 이 %보다 낮으면 추천하지 않음


def assumes_debt(signals: list[dict[str, Any]]) -> bool:
    """낙찰 뒤 떠안는 돈이 있을 수 있음(T1 선순위 임차인·전세권 등, 심각·높음) — 추천·모아 보기·계산이 같이 씀.
    이런 물건의 「싸다」는 떠안는 돈을 뺀 값이 아니라서 추천·「시세보다 싸게」에 넣지 않음(11/9)."""
    return any(
        s.get("ftype") == "T1"
        and s.get("level") in ("fatal", "high")
        and s.get("status") not in ("없음", "모름")
        for s in signals
    )


def overvalued(
    appraisal_krw: int | None,
    min_price_krw: int | None,
    failed: int | None,
    analysis: dict[str, Any],
) -> bool:
    """시세가 없는데 많이 유찰됐거나 감정가의 30% 아래 = 시장이 감정가를 인정하지 않은 물건(11/9)."""
    if not appraisal_krw or not min_price_krw or (analysis.get("market") or {}).get("price_krw"):
        return False
    return (
        failed or 0
    ) >= OVERVALUED_FAILS or min_price_krw * 100 < appraisal_krw * OVERVALUED_RATE


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


def expected_price(app: int, mn: int, analysis: dict[str, Any]) -> int:
    """예상 낙찰가 = 감정가 × 예상 낙찰가율 가운데(sale_rate.adjusted_rates — 상세와 같은 셈, 11/8).
    율을 모르면 최저가. 추천(PICK-01)과 모아 보기(COLLECT-01)가 같이 씀."""
    r = adjusted_rates(analysis.get("sale_rate"), analysis.get("court_cell"), app, mn)
    return max(mn, round(app * r["mid"] / 100)) if r and app else mn


# 용도 글자 → 종류. 위에서부터 처음 맞는 것(11/9 — 찾기 SQL 도 이 표로 만들어 카드 종류와 찾기 결과가 같음).
# 「상가,오피스텔,근린시설」 묶음은 상가로(11/4 — 오피스텔로 잘못 높게 쳤음)
KIND_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("apt", ("아파트",)),
    ("shop", ("근린", "상가", "판매")),
    ("officetel", ("오피스텔",)),
    ("villa", ("다세대", "연립", "빌라")),
    ("house", ("단독", "다가구")),
    ("shop", ("업무", "사무")),
    ("land", ("대지", "임야", "전", "답", "토지")),
)


def usage_kind(usage: str | None) -> str:
    """용도 글자 → 종류(apt·officetel·villa·house·shop·land·etc). 추천·유찰 기록(WAIT-01)·찾기가 같이 씀."""
    u = usage or ""
    for kind, words in KIND_RULES:
        if any(w in u for w in words):
            return kind
    return "etc"


def pick_score(x: PickInput, purpose: str | None = None) -> RuleResult:
    """물건 하나의 추천 점수(0~100)와 이유. value = {score, excluded, reasons, parts}. purpose: live·rent·invest·None."""
    if purpose == "resell":  # 시작 질문 「매도(되팔기)」 = 투자
        purpose = "invest"
    w = WEIGHTS.get(purpose, WEIGHTS[None])
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
    elif assumes_debt(signals):
        excluded = "떠안는 돈 있음"
    elif overvalued(app, mn, x.failed_count, a):
        # 시세가 없는데 많이 유찰됐거나 감정가의 30% 아래 = 시장이 감정가를 인정하지 않은 물건(11/9 —
        # 수원 2024타경101239: 감정가 1.16억 → 9번 유찰 · 같은 건물이 감정가 17%에 팔림). 찾기에는 그대로.
        excluded = "시세 없이 많이 유찰"

    # ── 싼 정도: 예상 낙찰가(감정가 × 중앙 낙찰가율, 최저가보다 낮을 수 없음) vs 시세. 25% 싸면 1
    expect = expected_price(app, mn, a)
    market = (a.get("market") or {}).get("price_krw")
    if market and expect:
        gap = market - expect
        r_value = _clamp(gap / market / 0.25)
        if gap >= 10_000_000:
            reasons.append(f"시세보다 {_won_short(gap)} 낮게 살 여지")
    elif app and mn:
        # 시세가 없으면 감정가 대비로만 — 믿을 만하지 않아 낮게. 유찰이 많을수록 「싸다」가 아니라
        # 「감정가가 높게 잡혔다」는 뜻이라 2회부터 깎음(11/9)
        stale = _clamp(1 - max(0, (x.failed_count or 0) - 1) / 4)
        r_value = 0.35 * _clamp((app - mn) / app / 0.5) * stale
    else:
        r_value = 0.0

    # ── 안전: 25 에서 깎아 비율로
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
    r_safety = max(0.0, safety) / 25
    unknown = any(s.get("status") == "모름" for s in signals)
    if (
        not flagged and not unknown and safety >= 20
    ):  # 「미확인」이 있으면 「위험 없음」이라 하지 않음(11/9)
        reasons.append("위험 신호 없음")

    # ── 목적에 맞는 집(20점 표를 비율로)
    kind = usage_kind(x.usage)
    area = x.area_m2 or 0
    redev = bool(a.get("redev"))
    fc = x.failed_count or 0
    disc = (app - mn) / app if app else 0
    fit_pts = {
        "live": (12 if kind == "apt" else 7 if kind in ("officetel", "villa") else 2)
        + (8 if 40 <= area <= 110 else 3 if area else 0),
        "rent": (12 if kind in ("officetel", "villa") else 8 if kind == "apt" else 6 if kind == "shop" else 3)
        + (8 if 0 < area <= 60 else 3),
        "invest": (10 if redev else 0) + (5 if fc >= 2 else 0) + (5 if disc >= 0.3 else 0),
    }  # fmt: skip
    # 감정평가 요항의 역·초등학교(11/4) — 실거주는 +3·+1, 임대는 역만 +2 (20점 안에서)
    ap = a.get("appraisal") or {}
    bonus = {"live": (3 if ap.get("near_station") else 0) + (1 if ap.get("near_school") else 0),
             "rent": 2 if ap.get("near_station") else 0}.get(purpose or "", 0)  # fmt: skip
    r_fit = min(20, fit_pts.get(purpose or "", 0) + bonus) / 20
    if purpose == "live" and ap.get("near_station"):
        reasons.append(f"{ap['near_station']} 가까움")
    if redev and purpose in ("invest", None):
        reasons.append("재개발·재건축 구역")

    # ── 임대 수익률(임대 목적만): 월세×12 ÷ (예상 낙찰가 − 월세 보증금). 3% 0 → 7% 1, 모르면 0.3
    r_yield = 0.3
    rent_m, rent_d = (x.rent or {}).get("monthly_krw"), (x.rent or {}).get("deposit_krw") or 0
    if rent_m and expect and expect > rent_d:
        y = rent_m * 12 / (expect - rent_d)
        r_yield = _clamp((y - 0.03) / 0.04)
        if purpose == "rent":
            reasons.insert(0, f"월세 수익률 약 {y * 100:.1f}%")

    # ── 경쟁이 덜함: 같은 법원 비슷한 물건 낙찰가율 가운데값이 낮을수록
    cc = a.get("court_cell") or {}
    r_comp = _clamp((110 - float(cc["p50"])) / 40) if cc.get("p50") else 0.5

    # ── 때: 유찰 뒤 0.4 · 새 물건 0.2 · 준비 시간 넉넉(14~35일) 0.4
    d = x.d_day
    days_r = (
        1.0
        if d is not None and 14 <= d <= 35
        else 0.5
        if d is not None and (10 <= d < 14 or 35 < d <= 45)
        else 0.0
    )
    r_timing = (0.4 if fc >= 1 else 0) + (0.2 if a.get("new_item") else 0) + 0.4 * days_r
    if fc >= 1 and app and mn:
        reasons.append(f"유찰 {fc}회 · 감정가의 {round(mn * 100 / app)}%")

    ratios = {
        "value": r_value,
        "safety": r_safety,
        "fit": r_fit,
        "yield": r_yield,
        "comp": r_comp,
        "timing": r_timing,
    }
    parts = {k: round(w[k] * r, 1) for k, r in ratios.items() if w[k]}
    score = round(sum(parts.values()))
    return RuleResult(
        value={"score": 0 if excluded else score, "excluded": excluded, "reasons": reasons[:2], "parts": parts},
        status=Status.ESTIMATED,
        rule_id=RULE_ID,
        evidence=[{"expect_krw": expect, "market_krw": market, "court_p50": cc.get("p50"), "purpose": purpose}],
    )  # fmt: skip


def case_key(r: dict[str, Any]) -> str:
    """같은 사건(일괄·여러 호실)을 하나로 보는 열쇠 — 공매는 물건마다."""
    if r.get("case_no"):
        return f"{r.get('court')}|{r.get('case_no')}"
    return str(r.get("item_id") or id(r))


def diversify(
    rows: list[dict[str, Any]], n: int, per_gu: int = 2, skip_cases: set[str] | None = None
) -> list[dict[str, Any]]:
    """점수 순 목록에서 같은 사건·같은 단지는 1건, 같은 구는 per_gu 건까지만 골라 n 건.
    skip_cases: 앞 칸에 이미 나온 사건(같은 사건의 다른 호실이 또 나오지 않게, 11/9)."""
    out: list[dict[str, Any]] = []
    seen_bld: set[str] = set()
    seen_case: set[str] = set(skip_cases or ())
    gu_n: dict[str, int] = {}
    for r in rows:
        bld = f"{r.get('place')}|{r.get('building')}"
        gu = str(r.get("place") or "")
        if case_key(r) in seen_case:
            continue
        if r.get("building") and bld in seen_bld:
            continue
        if gu_n.get(gu, 0) >= per_gu:
            continue
        out.append(r)
        seen_bld.add(bld)
        seen_case.add(case_key(r))
        gu_n[gu] = gu_n.get(gu, 0) + 1
        if len(out) >= n:
            break
    return out


# 미리 매겨 두는 목적들(11/14) — None 은 로그인 전(목적 없이 점수 순). 표에는 "" 로 적음
SCORE_PURPOSES: tuple[str | None, ...] = (None, "live", "rent", "invest")


def score_row(r: dict[str, Any], purpose: str | None, today: date) -> dict[str, Any]:
    """DB 물건 한 줄 → pick_score 값. 홈(그때 셈)과 수집기(미리 매김)가 같은 재료로 부르게 한 곳.

    r: usage_name · appraisal_krw · min_price_krw · failed_count · building_area_m2 · is_share ·
    is_special_case · analysis · sale_date · (임대 목적만) rent_monthly · rent_deposit."""
    value: dict[str, Any] = pick_score(
        PickInput(
            usage=r["usage_name"], appraisal_krw=r["appraisal_krw"], min_price_krw=r["min_price_krw"],
            failed_count=r["failed_count"],
            area_m2=float(r["building_area_m2"]) if r["building_area_m2"] else None,
            is_share=bool(r["is_share"]), is_special=bool(r["is_special_case"]),
            analysis=r["analysis"] or {},
            d_day=(r["sale_date"] - today).days if r["sale_date"] else None,
            rent={"monthly_krw": r.get("rent_monthly"), "deposit_krw": r.get("rent_deposit")},
        ),
        purpose,
    ).value  # fmt: skip
    return value
