"""원천 사이트 예의 규칙을 한 곳에서 강제합니다.

- 요청 사이 1초, 사건 사이 3초 (줄이지 않음)
- 이상 응답은 3번까지만 다시 시도, 그래도 이상하면 전체 중단 (우회하지 않음)
- 하루 한도를 넘기면 중단
"""

import time
from collections.abc import Callable
from typing import Any

REQUEST_GAP_SEC = 1.0
CASE_GAP_SEC = 3.0
RETRIES = 3


class Blocked(Exception):
    """원천이 이상하게 답함 → 그날 수집을 멈춥니다."""


class DailyLimitReached(Exception):
    """하루 한도에 닿음."""


class Polite:
    def __init__(self, daily_limit: int | None = None, sleep: Callable[[float], None] = time.sleep):
        self.daily_limit = daily_limit
        self.count = 0
        self._sleep = sleep
        self._last = 0.0

    def call(self, fn: Callable[[], dict[str, Any]], what: str) -> dict[str, Any]:
        """fn 은 {"ok": bool, ...} 을 돌려주는 요청 한 번."""
        if self.daily_limit is not None and self.count >= self.daily_limit:
            raise DailyLimitReached(f"하루 한도 {self.daily_limit}건")
        res: dict[str, Any] = {}
        for attempt in range(RETRIES):
            gap = REQUEST_GAP_SEC - (time.monotonic() - self._last)
            if gap > 0:
                self._sleep(gap)
            res = fn()
            self._last = time.monotonic()
            self.count += 1
            if res.get("ok"):
                return res
            self._sleep(1.5 * (attempt + 1))
        raise Blocked(
            f"{what}: 응답 이상 (status {res.get('status')}) {str(res.get('msg', ''))[:120]}"
        )

    def between_cases(self) -> None:
        self._sleep(CASE_GAP_SEC)
