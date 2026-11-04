"""원천 사이트 예의 규칙을 한 곳에서 강제합니다.

11/4 법원이 집 IP 를 「비정상 IP」로 막음 → 더 느리고 적게:
- 요청 사이 2.5초 + 0~1초 흔들림, 사건 사이 6초 + 0~3초 (줄이지 않음)
- 법원 전체 하루 요청 한도(모든 수집기 합): logs/court_budget.json 에 그날 센 수를 함께 씀
- 11/4 저녁 「하루 종일 고르게」: 한도를 법원 서비스 시간(06~24시, 18시간)으로 나눠 시간마다 몫만 씀
  (아침 목록 수집처럼 한 번에 끝내야 하는 것은 hourly=False). 한도는 고정이 아님 —
  7일 연속 막히지 않으면 20% 올리고, 막히면 40% 내림(법원이 견디는 만큼만, 2,500번은 시작점일 뿐)
- 이상 응답은 3번까지만 다시 시도, 그래도 이상하면 전체 중단하고 logs/court_blocked.txt 를 남김
  → 그 뒤 1시간(같은 날 또 막히면 2·4시간)은 법원 수집기가 켜지자마자 멈춤. 풀렸으면 이 파일을 지우면 됨
- 하루 한도를 넘기면 중단
"""

import json
import math
import os
import random
import time
from collections.abc import Callable
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

REQUEST_GAP_SEC = 2.5
CASE_GAP_SEC = 6.0
RETRIES = 3
SITE_DAY_MAX = {"court": 2500}  # 시작 한도(하루 요청 수, 모든 수집기 합) — 사건 하나에 6~7번
CAP_MIN, CAP_MAX = 800, 20000
GROW_AFTER_DAYS, GROW, SHRINK = 7, 1.2, 0.6
SERVICE_HOURS = 18  # 법원 06:00~24:00
# 막히면 쉬는 시간(11/4 저녁): 1시간 → 같은 날 또 막히면 2시간 → 4시간까지. 다시 시작할 때는 새 브라우저(새 세션)이고
# 한도는 막힐 때마다 40% 낮춤. 법원 막힘은 IP 보다 세션(쿠키) 단위라는 다른 수집기의 실측을 따름.
BLOCK_BASE_HOURS, BLOCK_MAX_HOURS = 1, 4
LOGS = Path(__file__).resolve().parents[4] / "logs"


class Blocked(Exception):
    """원천이 이상하게 답함 → 그날 수집을 멈춥니다."""


class DailyLimitReached(Exception):
    """하루 한도에 닿음."""


def _block_file(site: str) -> Path:
    return LOGS / f"{site}_blocked.txt"


def _budget_file(site: str) -> Path:
    return LOGS / f"{site}_budget.json"


def roll(b: dict[str, Any], today: str, start_cap: int) -> dict[str, Any]:
    """하루가 바뀌면 센 수를 0으로 — 어제 안 막혔으면 무사한 날 +1, 7일 모이면 한도 20% 올림."""
    if b.get("date") == today:
        b.setdefault("cap", start_cap)
        b.setdefault("hours", {})
        return b
    cap, ok = int(b.get("cap") or start_cap), int(b.get("ok_days") or 0)
    if b.get("date") and not b.get("blocked"):
        ok += 1
        if ok >= GROW_AFTER_DAYS:
            cap, ok = min(CAP_MAX, int(cap * GROW)), 0
    return {"date": today, "count": 0, "hours": {}, "cap": cap, "ok_days": ok, "blocked": False}


def pause_hours(blocks_today: int) -> int:
    """그날 몇 번째 막힘인지 → 쉬는 시간(1·2·4시간)."""
    return min(BLOCK_MAX_HOURS, BLOCK_BASE_HOURS * 2 ** max(0, blocks_today - 1))


def _save(f: Path, b: dict[str, Any]) -> None:
    """한 번에 바꿔 씀(임시 파일 → 바꿔치기) — 쓰는 도중 다른 수집기가 빈 파일을 읽지 않게."""
    LOGS.mkdir(exist_ok=True)
    tmp = f.with_suffix(f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(b), encoding="utf-8")
    for _ in range(10):
        try:
            os.replace(tmp, f)
            return
        except PermissionError:  # 윈도에서 다른 수집기가 막 읽는 중
            time.sleep(0.1)
    tmp.unlink(missing_ok=True)


def hour_share(cap: int) -> int:
    """한 시간에 쓸 몫 — 하루 한도를 서비스 시간으로 나눔."""
    return math.ceil(cap / SERVICE_HOURS)


class Polite:
    def __init__(
        self,
        daily_limit: int | None = None,
        sleep: Callable[[float], None] = time.sleep,
        site: str | None = "court",
        jitter: bool = True,
        hourly: bool = True,
    ):
        self.daily_limit = daily_limit
        self.count = 0
        self._sleep = sleep
        self._last = 0.0
        self.site = site
        self._jitter = jitter
        self.hourly = hourly
        # 매시 작업(court_hourly)이 단계마다 시간 몫을 나눠 줌 — 한 단계가 몫을 다 써서 뒤 단계가 굶지 않게(11/5)
        step = os.environ.get("AUCS_STEP_REQ")
        self.step_max = int(step) if step and step.isdigit() else None
        if site:
            f = _block_file(site)
            if f.exists():
                at = datetime.fromtimestamp(f.stat().st_mtime)
                hours = pause_hours(self._blocks_today())
                if datetime.now() - at < timedelta(hours=hours):
                    raise Blocked(
                        f"{site} 이 {at:%m-%d %H:%M} 에 막음 — {hours}시간 쉼 ({f} 를 지우면 다시 시작)"
                    )

    def _blocks_today(self) -> int:
        if not SITE_DAY_MAX.get(self.site or ""):
            return 1
        try:
            b = json.loads(_budget_file(self.site or "").read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return 1
        return int(b.get("blocks") or 1) if b.get("date") == date.today().isoformat() else 1

    def _j(self, n: float) -> float:
        return random.uniform(0, n) if self._jitter else 0.0

    def _load(self) -> tuple[Path, dict[str, Any]]:
        f = _budget_file(self.site or "")
        b: dict[str, Any] = {}
        for _ in range(
            5
        ):  # 다른 수집기가 쓰는 찰나에 읽으면 비어 보임(11/5 아침 0바이트) — 잠깐 뒤 다시
            try:
                b = json.loads(f.read_text(encoding="utf-8"))
                break
            except FileNotFoundError:
                break
            except Exception:  # noqa: BLE001
                time.sleep(0.2)
        return f, roll(b, date.today().isoformat(), SITE_DAY_MAX.get(self.site or "", 0))

    def _spend(self) -> None:
        """사이트 전체 하루 한도와 이번 시간 몫(수집기 여럿이 함께 씀)."""
        if not SITE_DAY_MAX.get(self.site or ""):
            return
        f, b = self._load()
        # 수집기 여럿이 동시에 돌아도(매시 작업 + 5분마다 손님 요청) 법원 쪽에서 보면 간격이 지켜지게
        wait = REQUEST_GAP_SEC - (time.time() - float(b.get("last_ts") or 0))
        if wait > 0:
            self._sleep(wait)
            f, b = self._load()
        cap = int(b["cap"])
        if b["count"] >= cap:
            raise DailyLimitReached(f"{self.site} 하루 전체 한도 {cap}번")
        hh = f"{datetime.now():%H}"
        if self.hourly and b["hours"].get(hh, 0) >= hour_share(cap):
            raise DailyLimitReached(
                f"{self.site} 이번 시간 몫 {hour_share(cap)}번 — 다음 시간에 이어서"
            )
        b["count"] += 1
        b["hours"][hh] = b["hours"].get(hh, 0) + 1
        b["last_ts"] = time.time()
        _save(f, b)

    def _shrink(self) -> None:
        """막힘 → 한도 40% 내리고 무사한 날 0부터."""
        if not SITE_DAY_MAX.get(self.site or ""):
            return
        f, b = self._load()
        b.update(cap=max(CAP_MIN, int(int(b["cap"]) * SHRINK)), ok_days=0, blocked=True,
                 blocks=int(b.get("blocks") or 0) + 1)  # fmt: skip
        _save(f, b)

    def call(self, fn: Callable[[], dict[str, Any]], what: str) -> dict[str, Any]:
        """fn 은 {"ok": bool, ...} 을 돌려주는 요청 한 번."""
        if self.daily_limit is not None and self.count >= self.daily_limit:
            raise DailyLimitReached(f"하루 한도 {self.daily_limit}건")
        if (
            self.step_max is not None and self.count >= self.step_max
        ):  # 매시 작업이 단계마다 나눠 준 몫
            raise DailyLimitReached(f"이 단계 몫 {self.step_max}번 — 다음 단계로")
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
            self._shrink()
            LOGS.mkdir(exist_ok=True)
            _block_file(self.site).write_text(
                f"{datetime.now():%Y-%m-%d %H:%M} {what}\n", encoding="utf-8"
            )
        raise Blocked(
            f"{what}: 응답 이상 (status {res.get('status')}) {str(res.get('msg', ''))[:120]}"
        )

    def between_cases(self) -> None:
        self._sleep(CASE_GAP_SEC + self._j(3.0))
