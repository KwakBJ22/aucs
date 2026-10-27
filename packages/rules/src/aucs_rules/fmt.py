"""금액 글자 (10/28 정리: api·workers 에 따로 있던 won() 4개를 여기로 모음). 순수 함수."""


def man_text(v: int) -> str:
    """「7억 1,050만」 꼴. 만 원 아래는 버림(0이면 「0만」)."""
    eok, man = divmod(v // 10_000, 10_000)
    if eok and man:
        return f"{eok}억 {man:,}만"
    return f"{eok}억" if eok else f"{man:,}만"


def won(v: int | None, empty: str = "-") -> str:
    """화면 금액. 없거나 0이면 empty."""
    return man_text(v) if v else empty


def won_small(n: int) -> str:
    """만 원이 안 되는 금액은 원 단위로(등기부 배당표): 「8,000원」, 그 위는 man_text."""
    return f"{n:,}원" if 0 <= n < 10_000 else man_text(n)


def won_unit(v: int) -> str:
    """알림 글처럼 「원」을 붙임: 「1억 6,940만원」."""
    return man_text(v) + "원"
