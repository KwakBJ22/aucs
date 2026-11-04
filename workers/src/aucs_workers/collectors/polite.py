"""원천 사이트 예의 규칙을 한 곳에서 강제합니다.

11/4 법원이 집 IP 를 「비정상 IP」로 막음 → 더 느리고 적게:
- 요청 사이 2.5초 + 0~1초 흔들림, 사건 사이 6초 + 0~3초 (줄이지 않음)
- 법원 전체 하루 요청 한도(모든 수집기 합): logs/court_budget.json 에 그날 센 수를 함께 씀
- 이상 응답은 3번까지만 다시 시도, 그래도 이상하면 전체 중단하고 logs/court_blocked.txt 를 남김
  → 그 뒤 12시간은 법원 수집기가 켜지자마자 멈춤(막힌 동안 두드리지 않게). 풀렸으면 이 파일을 지우면 됨
- 하루 한도를 넘기면 중단
"""

import json
import random
import time
from collections.abc import Callable
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

REQUEST_GAP_SEC = 2.5
CASE_GAP_SEC = 6.0
RETRIES = 3
SITE_DAY_MAX = {"court": 2500}  # 하루 요청 수(모든 수집기 합) — 사건 하나에 6~7번
BLOCK_HOURS = 12
LOGS = Path(__file__).resolve().parents[4] / "logs"


class Blocked(Exception):
    """원천이 이상하게 답함 → 그날 수집을 멈춥니다."""


class DailyLimitReached(Exception):
    """하루 한도에 닿음."""


def _block_file(site: str) -> Path:
    return LOGS / f"{site}_blocked.txt"


def _budget_file(site: str) -> Path:
    return LOGS / f"{site}_budget.json"


class Polite:
    def __init__(
        self,
        daily_limit: int | None = None,
        sleep: Callable[[float], None] = time.sleep,
        site: str | None = "court",
        jitter: bool = True,
    ):
        self.daily_limit = daily_limit
        self.count = 0
        self._sleep = sleep
        self._last = 0.0
        self.site = site
        self._jitter = jitter
        if site:
            f = _block_file(site)
            if f.exists():
                at = datetime.fromtimestamp(f.stat().st_mtime)
                if datetime.now() - at < timedelta(hours=BLOCK_HOURS):
                    raise Blocked(
                        f"{site} 이 {at:%m-%d %H:%M} 에 막음 — {BLOCK_HOURS}시간 쉼 ({f} 를 지우면 다시 시작)"
                    )

    def _j(self, n: float) -> float:
        return random.uniform(0, n) if self._jitter else 0.0

    def _spend(self) -> None:
        """사이트 전체 하루 한도(수집기 여럿이 함께 씀)."""
        cap = SITE_DAY_MAX.get(self.site or "")
        if not cap:
            return
        f = _budget_file(self.site or "")
        today = date.today().isoformat()
        try:
            b = json.loads(f.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001 — 처음이거나 깨졌으면 0부터
            b = {}
        n = int(b.get("count", 0)) if b.get("date") == today else 0
        if n >= cap:
            raise DailyLimitReached(f"{self.site} 하루 전체 한도 {cap}번")
        LOGS.mkdir(exist_ok=True)
        f.write_text(json.dumps({"date": today, "count": n + 1}), encoding="utf-8")

    def call(self, fn: Callable[[], dict[str, Any]], what: str) -> dict[str, Any]:
        """fn 은 {"ok": bool, ...} 을 돌려주는 요청 한 번."""
        if self.daily_limit is not None and self.count >= self.daily_limit:
            raise DailyLimitReached(f"하루 한도 {self.daily_limit}건")
        res: dict[str, Any] = {}
        for attempt in range(RETRIES):
            gap = REQUEST_GAP_SEC + self._j(1.0) - (time.monotonic() - self._last)
            if gap > 0:
                self._sleep(gap)
            self._spend()
            res = fn()
            self._last = time.monotonic()
            self.count += 1
            if res.get("ok"):
                return res
            if "비정상" in str(res.get("msg", "")):  # 「비정상 IP」 — 다시 시도하지 않고 바로 멈춤
                break
            self._sleep(3.0 * (attempt + 1))
        if self.site:
            LOGS.mkdir(exist_ok=True)
            _block_file(self.site).write_text(
                f"{datetime.now():%Y-%m-%d %H:%M} {what}\n", encoding="utf-8"
            )
        raise Blocked(
            f"{what}: 응답 이상 (status {res.get('status')}) {str(res.get('msg', ''))[:120]}"
        )

    def between_cases(self) -> None:
        self._sleep(CASE_GAP_SEC + self._j(3.0))
