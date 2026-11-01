"""크롬 켜기(11/1): PC가 막 켜진 아침에 크롬이 스스로 업데이트하는 중이면 켜자마자 꺼짐
(TargetClosedError) → 20초 쉬고 세 번까지 다시 켬."""

import time
from typing import Any


def launch_chrome(p: Any, *, headless: bool = True, tries: int = 3, wait: float = 20) -> Any:
    for n in range(1, tries + 1):
        try:
            return p.chromium.launch(channel="chrome", headless=headless)  # 설치된 크롬
        except Exception as e:  # noqa: BLE001
            if n == tries:
                raise
            print(
                f"   크롬이 켜지다 꺼짐({type(e).__name__}) — {wait:.0f}초 뒤 다시({n}/{tries})",
                flush=True,
            )
            time.sleep(wait)
    raise RuntimeError("unreachable")
