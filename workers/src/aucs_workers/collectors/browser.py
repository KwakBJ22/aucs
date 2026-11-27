"""크롬 켜기(11/1): PC가 막 켜진 아침에 크롬이 스스로 업데이트하는 중이면 켜자마자 꺼짐
(TargetClosedError) → 20초 쉬고 세 번까지 다시 켬."""

import time
from typing import Any

# 창을 화면 밖에 띄움(11/7): 창 없는 크롬에서는 KAPA 감정평가서 화면이 비어 나옴 → 사람이 쓰는 보통 크롬 그대로, 창만 안 보이게
OFFSCREEN_ARGS = ["--window-position=-3000,-3000", "--window-size=1000,900"]


# 11/27: 법원 화면을 열 때 사진 · 글꼴 · 동영상까지 다 받아 버리던 것(2번 PC 휴대폰 데이터 35GB) — 우리가 쓰는 건 글 자료뿐.
# 법원이 주는 사진은 물건상세 JSON 안에 들어 있어 이걸 막아도 그대로 받음.
LEAN_TYPES = {"image", "font", "media"}


def lean_context(browser: Any) -> Any:
    """사진 · 글꼴 · 동영상은 받지 않는 창 묶음. 같은 묶음의 창끼리는 한 번 받은 화면 파일을 다시 쓰므로 창마다 새로 받지 않음."""
    ctx = browser.new_context()
    ctx.route(
        "**/*",
        lambda route: route.abort()
        if route.request.resource_type in LEAN_TYPES
        else route.continue_(),
    )
    return ctx


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
