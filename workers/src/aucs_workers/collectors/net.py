"""바깥 서버가 응답 중에 연결을 한 번 끊는 일(11/21 법원 전국 보관 · 11/22 브이월드)에 단계 전체가 실패하지 않게.

연결이 끊기거나 시간이 넘으면(httpx.TransportError) 1분 · 2분 쉬고 다시 — 세 번째도 안 되면 그대로 오류.
HTTP 오류 코드(한도 · 인증)는 다시 묻지 않음 — 받은 답이 있으니 부르는 쪽이 판단.
"""

import time
from collections.abc import Callable
from typing import Any

import httpx

TRIES = 3
WAIT_SEC = 60.0


def get_retry(
    client: httpx.Client,
    url: str,
    *,
    params: dict[str, Any] | None = None,
    tries: int = TRIES,
    wait: float = WAIT_SEC,
    sleep: Callable[[float], None] = time.sleep,
) -> httpx.Response:
    for n in range(1, tries + 1):
        try:
            return client.get(url, params=params)
        except httpx.TransportError as e:
            if n == tries:
                raise
            print(
                f"   연결 끊김({type(e).__name__}) — {wait * n:.0f}초 뒤 다시({n}/{tries - 1})",
                flush=True,
            )
            sleep(wait * n)
    raise AssertionError("닿지 않음")
