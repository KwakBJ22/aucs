"""개인 이름 가리기. 원본은 내부에만 두고 화면에는 가린 값만 씁니다."""

import re

_ROLE = r"(임차인|채무자|소유자|점유자|채권자|신청인|상대방|낙찰자|매수인|채무자겸소유자)"
_PATTERN = re.compile(_ROLE + r"\s*([가-힣])[가-힣]{1,3}")


def mask_names(text: str | None) -> str:
    """「임차인 홍길동」 → 「임차인 홍○○」."""
    return _PATTERN.sub(r"\1 \2○○", text or "")
