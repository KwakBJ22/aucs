"""입찰표 점검 (BID-01, 04탭 6절 T6). 자릿수 실수로 보증금을 잃는 일을 막습니다.

최저가 미만은 무효, 최저가의 2배를 넘으면 멈추고 다시 확인. 실제 손해 사례는 대부분 10배 이상.
재매각 물건은 법원이 정한 보증금 비율(보통 20~30%)을 씁니다 — 비율은 인자.
"""

from aucs_rules.result import RuleResult, Status

_DIGIT = "영일이삼사오육칠팔구"
_SMALL = ["", "십", "백", "천"]
_BIG = ["", "만", "억", "조"]


def korean_amount(n: int) -> str:
    """412000000 → 「사억일천이백만원」. 입찰표 금액란을 소리 내 읽어 보기 위한 표기."""
    if n <= 0:
        return "영원"
    parts: list[str] = []
    gi = 0
    while n:
        n, g = divmod(n, 10_000)
        if g:
            s = ""
            for i in range(3, -1, -1):
                d = (g // 10**i) % 10
                if d:
                    s += _DIGIT[d] + _SMALL[i]
            parts.append(s + _BIG[gi])
        gi += 1
    return "".join(reversed(parts)) + "원"


def check(
    bid_krw: int,
    min_price_krw: int,
    *,
    deposit_rate_pct: float = 10.0,
    resale: bool = False,
) -> RuleResult:
    """입찰가 점검: 배율·한글 읽기·보증금. level = block(무효) / stop(다시 확인) / ok."""
    ratio = bid_krw / min_price_krw if min_price_krw else 0.0
    if bid_krw < min_price_krw:
        level, msg = "block", "최저가보다 낮아 무효예요"
    elif ratio > 2:
        level, msg = "stop", f"최저가의 {ratio:.1f}배예요. 숫자 자릿수를 다시 보세요"
    else:
        level, msg = "ok", f"최저가의 {ratio:.2f}배"
    rate = deposit_rate_pct
    deposit = -(-min_price_krw * int(rate * 100) // 10_000)  # 올림
    value = {
        "level": level,
        "message": msg,
        "ratio": round(ratio, 3),
        "korean": korean_amount(bid_krw),
        "deposit_krw": deposit,
        "deposit_rate_pct": rate,
        "resale": resale,
        "tips": ["가격을 고친 입찰표는 무효 — 새 용지에", "사건번호·물건번호 확인"],
    }
    status = Status.CONFIRMED if level == "block" else Status.ESTIMATED
    return RuleResult(value, status, f"bid_form.{level}", [{"min_price_krw": min_price_krw}])
