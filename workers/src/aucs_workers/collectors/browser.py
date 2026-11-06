"""크롬 켜기(11/1): PC가 막 켜진 아침에 크롬이 스스로 업데이트하는 중이면 켜자마자 꺼짐
(TargetClosedError) → 20초 쉬고 세 번까지 다시 켬."""

import time
from typing import Any

# 창을 화면 밖에 띄움(11/7): 창 없는 크롬에서는 KAPA 감정평가서 화면이 비어 나옴 → 사람이 쓰는 보통 크롬 그대로, 창만 안 보이게
OFFSCREEN_ARGS = ["--window-position=-3000,-3000", "--window-size=1000,900"]


def launch_chrome(
    p: Any, *, headless: bool = True, offscreen: bool = False, tries: int = 3, wait: float = 20
) -> Any:
    """설치된 크롬을 켬. offscreen 이면 창을 띄우되 화면 밖에(창 없는 크롬과 달리 화면이 다 그려짐)."""
    args = OFFSCREEN_ARGS if offscreen and not headless else []
    for n in range(1, tries + 1):
        try:
            return p.chromium.launch(channel="chrome", headless=headless, args=args)
        except Exception as e:  # noqa: BLE001
            if n == tries:
                raise
            print(
                f"   크롬이 켜지다 꺼짐({type(e).__name__}) — {wait:.0f}초 뒤 다시({n}/{tries})",
                flush=True,
            )
            time.sleep(wait)
    raise RuntimeError("unreachable")
