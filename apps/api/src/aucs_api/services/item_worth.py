"""「얼마짜리인가」: 감정가·시세 차이 이유, 낙찰 예상 범위"""

from typing import Any

from aucs_rules.fmt import won
from aucs_rules.sale_rate import restarted

# 감정가가 같은 단지 시세의 이 범위 밖이면 시세 비교를 빼고 이유를 한 줄로 (10/19 대표님)
APPRAISAL_SANE = (0.55, 1.6)


# 명세서에 적히면 감정가가 낮게 잡히는 사정
SPEC_WORDS = [
    "위반건축",
    "대지권",
    "토지별도등기",
    "별도등기",
    "유치권",
    "법정지상권",
    "제시외",
    "지분",
    "맹지",
]


def pct_range(lo: float, hi: float) -> str:
    """「73~73%」처럼 같은 수가 되면 하나만(11/1)."""
    a, b = round(lo), round(hi)
    return f"{a}%" if a == b else f"{a}~{b}%"


def appraisal_gap(
    r: dict[str, Any], signals: list[dict[str, Any]], spec_txt: str = ""
) -> tuple[str, str] | None:
    """감정가가 시세와 크게 다를 때 (이유 종류, 안내). 이유는 명세서 비고란·신호로 찾음.

    종류: share(지분) / special(특별조건) / note(비고란 있음) / none(이유 모름)."""
    mkt, app = r.get("market"), r.get("appraisal_krw")
    if not mkt or not app or not mkt.get("price_krw"):
        return None
    ratio = app / mkt["price_krw"]
    if APPRAISAL_SANE[0] <= ratio <= APPRAISAL_SANE[1]:
        return None
    ids = {s.get("rule_id") for s in signals if s.get("status") != "모름"}
    if ratio < 1 and (r.get("is_share") or "risk.share" in ids):
        return (
            "share",
            "지분만 파는 물건이라 감정가도 지분 몫이에요 · 단지 시세와 바로 비교하면 안 돼요",
        )
    if ratio > 1 and "risk.special_condition" in ids:
        return "special", "전세 피해 주택이라 감정가가 실제 거래보다 높게 잡혔을 수 있어요"
    found = next((w for w in SPEC_WORDS if w in spec_txt), None)
    if ratio < 1 and found:
        return (
            "spec",
            f"명세서에 「{found}」 내용이 있어요 · 감정가가 낮게 잡힌 이유일 수 있어요(명세서 원문 보기)",
        )
    deal = f"감정가가 같은 단지 거래({won(mkt['price_krw'])})와 크게 달라요"
    if (r.get("note_masked") or "").strip():
        return "note", f"{deal} · 비고란 조건을 먼저 보세요(「무엇을 사나」)"
    return "none", f"{deal} · 다른 평형 거래일 수도 있어요"


def worth(
    r: dict[str, Any], signals: list[dict[str, Any]], spec_txt: str = ""
) -> tuple[str, list[str], Any]:
    """「얼마짜리인가」 한 줄과 경고 줄. 관할 법원 칸이 기준을 바꾸면 범위를 그만큼 옮깁니다(입찰가 산정 1C~1E)."""
    rate, court, peers = r.get("sale_rate"), r.get("court_cell"), r.get("local_peers")
    notes: list[str] = []
    mkt, app, mn = r.get("market"), r.get("appraisal_krw"), r.get("min_price_krw")
    gap = appraisal_gap(r, signals, spec_txt)
    if gap:
        notes.append(gap[1])
        mkt = None
    # 「처음 나온 물건」은 최저가가 감정가 그대로일 때만 (유찰 수 자료가 빠진 물건이 있음)
    if restarted(r.get("failed_count"), app, mn):
        notes.append(
            f"유찰 {r['failed_count']}회 뒤 매각조건이 바뀌어 감정가부터 다시 시작해요(최저가=감정가)"
        )
    if r.get("new_item") and (not app or not mn or mn >= app):
        if gap:  # 감정가를 그대로 믿기 어려운 신건 → 「비싸게 팔려요」라고 하지 않음
            return (
                "처음 나온 물건이에요 · 감정가가 시세와 크게 달라 아래 안내를 먼저 보세요",
                notes,
                None,
            )
        if mkt and mkt["price_krw"] < app:
            return (
                f"처음 나온 물건이지만 시세({won(mkt['price_krw'])})가 감정가보다 낮아요",
                notes,
                None,
            )
        if restarted(r.get("failed_count"), app, mn):
            return "감정가부터 다시 시작한 물건이라 처음 나온 물건처럼 보면 돼요", notes, None
        return "처음 나온 물건이라 보통 감정가보다 비싸게 팔려요", notes, None
    if not rate:
        return "비교할 낙찰 사례가 부족해요", notes, None
    lo, mid, hi, shift = rate["p25"], rate["p50"], rate["p75"], 0.0
    if court and court.get("use_as_base"):
        shift = court["diff"]
        lo, mid, hi = lo + shift, mid + shift, hi + shift
        notes.append(
            f"이 법원은 같은 조건에서 {abs(round(shift))}%p {'높게' if shift > 0 else '낮게'} 팔려요"
        )
    if peers and peers.get("warn"):
        notes.append(
            f"같은 구 최근 {peers['n']}건은 {pct_range(peers['lo'], peers['hi'])}에 팔렸어요"
        )
    if not gap and any(s.get("rule_id") == "risk.low_appraisal" for s in signals):
        notes.append("감정가가 시세보다 낮아 더 높게 팔릴 수 있어요")
    # 최저가보다 낮게는 낙찰될 수 없음 → 범위 아래쪽을 최저가에 맞춤
    floor = mn / app * 100 if mn and app else None
    below = bool(floor and hi < floor)
    if floor:
        lo, mid, hi = max(lo, floor), max(mid, floor), max(hi, floor)
    ans = f"비슷한 물건은 감정가의 {pct_range(lo, hi)}에 낙찰됐어요"
    if below:
        ans = "비슷한 물건이 이번 최저가보다 싸게 팔려서 최저가 근처에서 낙찰될 것 같아요"
    elif mkt and app:
        a, b = app * lo / mkt["price_krw"], app * hi / mkt["price_krw"]
        ans = f"시세의 {pct_range(a, b)}쯤에 낙찰될 것 같아요"
    return ans, notes, {**rate, "p25": lo, "p50": mid, "p75": hi, "court_shift": shift}
