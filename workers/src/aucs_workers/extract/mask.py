"""개인 이름 가리기. 원본은 내부에만 두고 화면에는 가린 값만 씁니다.

역할 낱말 뒤의 「홀로 떨어진 2~4글자 한글」만 이름으로 봅니다.
「채권자 변경신청서」「채권자 승계통지서」처럼 뒤에 글자가 이어지거나 흔한 낱말이면 가리지 않습니다.
(분류는 가리기 전 원문으로 합니다.)
"""

import re

_ROLE = r"(임차인|채무자|소유자|점유자|채권자|신청인|상대방|낙찰자|매수인|채무자겸소유자|승계인)"
_PATTERN = re.compile(_ROLE + r"(\s+)(?!겸)([가-힣])([가-힣]{1,3})(?![가-힣])")
_NOT_NAME = {
    "겸소유자", "겸채무자", "대리인", "변경", "승계", "주식회사", "은행", "외", "등", "본인",
    "제출", "발송", "신청", "명의", "측", "회사", "조합", "공사", "보험",
}  # fmt: skip


def mask_names(text: str | None) -> str:
    """「임차인 홍길동」 → 「임차인 홍○○」."""

    def repl(m: re.Match[str]) -> str:
        word = m.group(3) + m.group(4)
        if word in _NOT_NAME or any(word.startswith(w) for w in _NOT_NAME if len(w) > 1):
            return m.group(0)
        return f"{m.group(1)}{m.group(2)}{m.group(3)}○○"

    return _PATTERN.sub(repl, text or "")
