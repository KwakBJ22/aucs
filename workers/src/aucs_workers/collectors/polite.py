"""원천 사이트 예의 규칙을 한 곳에서 강제합니다.

11/4 법원이 집 IP 를 「비정상 IP」로 막음 → 더 느리고 적게:
- 요청 사이 2.5초 + 0~1초 흔들림, 사건 사이 6초 + 0~3초 (줄이지 않음)
- 법원 전체 하루 요청 한도(모든 수집기 합): logs/court_budget.json 에 그날 센 수를 함께 씀
- 11/4 저녁 「하루 종일 고르게」: 한도를 법원 서비스 시간(06~24시, 18시간)으로 나눠 시간마다 몫만 씀
  (아침 목록 수집처럼 한 번에 끝내야 하는 것은 hourly=False). 한도는 고정이 아님 —
  3일 연속 막히지 않으면 20% 올리고, 막히면 20% 내림(11/20 — 법원이 견디는 만큼만, 2,500번은 시작점일 뿐)
- 이상 응답은 3번까지만 다시 시도, 그래도 이상하면 전체 중단하고 logs/court_blocked.txt 를 남김
  → 그 뒤 2시간(같은 날 또 막히면 4시간)은 법원 수집기가 켜지자마자 멈춤. 풀렸으면 이 파일을 지우면 됨
  (11/20 법원 문의: 막히면 1~2시간 뒤 풀림 — 1시간 만에 다시 묻다 또 막히면 한도가 한 번 더 깎여서 2시간부터)
- 하루 한도를 넘기면 중단
- 11/9 오래 막힘: 차단 기록 파일에 「until YYYY-MM-DD HH:MM」 줄이 있으면 그때까지 법원에 아예 묻지 않음.
  그 뒤 첫 요청이 하루 한 번의 「풀렸나」 확인 — 또 막히면 24시간 뒤로 다시 미룸(풀릴 때까지 하루 1번만 접속)
"""

import json
import math
import os
import random
import sys
import time
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

REQUEST_GAP_SEC = 2.5
CASE_GAP_SEC = 6.0
RETRIES = 3
# 11/21 · 11/22: 법원 요청이 「Failed to fetch」(연결 끊김)로 죽어 전국 보관 · 서류 보관 단계가 통째로 빠졌음
# → 연결 끊김만 1분 · 2분 쉬고 다시(모든 법원 수집기 공통). 막힘 · 한도는 그대로.
FETCH_TRIES, FETCH_WAIT_SEC = 3, 60.0
# 11/23 대표님: 한 시간에 모든 수집기 합이 이보다 많으면 다음 시간까지 기다림 — 막히지 않은 11/22 의 가장 많은 시간(07시)
# 매시 작업은 원래 시간 몫(하루 한도 ÷ 18)이 있으므로 이것은 아침 묶음 · 전국 보관처럼 몫 없이 도는 것에 걸림
HOUR_MAX_ALL = 861
# 11/26 대표님: 2번 PC(AUCS_ROLE=docs)는 하루 한도 · 시간 몫에 닿아도 멈추지 않음 — 언제 막히는지 재 보려고.
#   요청 간격(2.5초 + 흔들림 · 사건 사이 6초)은 그대로. 막히면 지금처럼 멈추고 차단 기록 줄에 그날 센 수를 남김.
#   한 차례가 다음 차례(매시 10분)를 넘지 않게 AUCS_DEADLINE(epoch 초)까지만 돎 — court_hourly.docs_main.
def uncapped() -> bool:
    return (os.environ.get("AUCS_ROLE") or "").strip().lower() == "docs"


SITE_DAY_MAX = {"court": 2500}  # 시작 한도(하루 요청 수, 모든 수집기 합) — 사건 하나에 6~7번
CAP_MIN, CAP_MAX = 800, 20000
# 11/18 대표님: 무사한 날 7일 → 3일마다 20% 올림(막힘은 요청 속도 탓이었음 — 간격은 그대로)
# 11/20 대표님: 막혀도 1~2시간이면 풀림(법원 문의) — 너무 조심하지 말고, 막히면 조금만 낮춤(40% → 20%)
GROW_AFTER_DAYS, GROW, SHRINK = 3, 1.2, 0.8
SERVICE_HOURS = 18  # 법원 06:00~24:00
# 막히면 쉬는 시간(11/4 저녁): 1시간 → 같은 날 또 막히면 2시간 → 4시간까지. 다시 시작할 때는 새 브라우저(새 세션)이고
# 한도는 막힐 때마다 20% 낮춤(11/20). 법원 막힘은 IP 보다 세션(쿠키) 단위라는 다른 수집기의 실측을 따름.
BLOCK_BASE_HOURS, BLOCK_MAX_HOURS = 2, 4
LOGS = Path(__file__).resolve().parents[4] / "logs"
# 11/21: 관리자 요청(5분 작업)으로 돈 전국 보관이 장부에 세계 표준시 「03」·「04」시로 적힘 — 프로세스 시계와
# 상관없이 날짜 · 시간 몫 · 막힘 시각은 늘 한국 시각으로 셈(한국은 서머타임 없음).
KST = timezone(timedelta(hours=9))


def now_kst() -> datetime:
    """한국 시각(시간대 없는 값 — 막힘 파일에 적힌 시각과 바로 견줌)."""
    return datetime.now(KST).replace(tzinfo=None)


class Blocked(Exception):
    """원천이 이상하게 답함 → 그날 수집을 멈춥니다."""


class DailyLimitReached(Exception):
    """하루 한도에 닿음."""


def _block_file(site: str) -> Path:
    return LOGS / f"{site}_blocked.txt"


def _budget_file(site: str) -> Path:
    return LOGS / f"{site}_budget.json"


def roll(b: dict[str, Any], today: str, start_cap: int) -> dict[str, Any]:
    """하루가 바뀌면 센 수를 0으로 — 어제 안 막혔으면 무사한 날 +1, 3일 모이면 한도 20% 올림.

    파일 날짜가 오늘보다 뒤면(시계가 늦은 곳 — UTC 인 대화창 VM 이 한국 0~9시에 읽을 때) 날이 바뀐 것으로
    보지 않음(11/18 사고: 두 날짜가 번갈아 써서 셈이 0이 되고 한도가 몇 분 만에 20,000 까지 오름).
    그래서 한도는 날짜가 앞으로 바뀔 때 한 번만 오름."""
    if b.get("date") == today or str(b.get("date") or "") > today:
        b.setdefault("cap", start_cap)
        b.setdefault("hours", {})
        return b
    cap, ok = int(b.get("cap") or start_cap), int(b.get("ok_days") or 0)
    if b.get("date") and not b.get("blocked"):
        ok += 1
        if ok >= GROW_AFTER_DAYS:
            cap, ok = min(CAP_MAX, int(cap * GROW)), 0
    return {"date": today, "count": 0, "hours": {}, "cap": cap, "ok_days": ok, "blocked": False}


DAILY_CHECK_HOURS = 24


def read_until(text: str) -> datetime | None:
    """차단 기록의 「until 2026-11-10 09:00」 줄 → 그 시각. 없으면 None(순수 함수)."""
    for line in text.splitlines():
        if line.startswith("until "):
            try:
                return datetime.strptime(line[6:].strip(), "%Y-%m-%d %H:%M")
            except ValueError:
                return None
    return None


def pause_hours(blocks_today: int) -> int:
    """그날 몇 번째 막힘인지 → 쉬는 시간(2·4시간)."""
    return min(BLOCK_MAX_HOURS, BLOCK_BASE_HOURS * 2 ** max(0, blocks_today - 1))


# 이 수집기 이름(단계별 요청 수) — 「court_docs --archive」처럼 모듈 이름과 -- 옵션
STEP = " ".join([Path(sys.argv[0]).stem] + [a for a in sys.argv[1:] if a.startswith("--")])


def _keep_history(site: str, b: dict[str, Any]) -> None:
    """날이 바뀔 때 어제 장부를 한 줄 남김(11/23 — 장부는 날마다 새로 써서 지난날 시간별 수를 몰랐음).
    여러 수집기가 같이 바꾸면 같은 날이 두 줄 남을 수 있음 — 읽을 때 날짜로 하나만."""
    try:
        LOGS.mkdir(exist_ok=True)
        with (LOGS / f"{site}_budget_history.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(b, ensure_ascii=False) + "\n")
    except OSError:
        pass


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
        gap: float | None = None,
    ):
        # 요청 간격(초) — 전국 보관은 천천히(11/23, 2.5 → 5초)
        self.gap = max(REQUEST_GAP_SEC, gap or 0.0)
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
            until = read_until(f.read_text(encoding="utf-8")) if f.exists() else None
            if until is not None:
                if now_kst() < until:
                    raise Blocked(f"{site} 오래 막힘 — {until:%m-%d %H:%M} 까지 묻지 않음 ({f})")
                # 지난 뒤 첫 요청이 하루 한 번의 확인(막혀 있으면 call 이 24시간 뒤로 다시 미룸)
            elif f.exists():
                at = datetime.fromtimestamp(f.stat().st_mtime, KST).replace(tzinfo=None)
                hours = pause_hours(self._blocks_today())
                if now_kst() - at < timedelta(hours=hours):
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
        return int(b.get("blocks") or 1) if b.get("date") == now_kst().date().isoformat() else 1

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
        today = now_kst().date().isoformat()
        new = roll(b, today, SITE_DAY_MAX.get(self.site or "", 0))
        if b.get("date") and str(b["date"]) < today and new.get("date") == today:
            _keep_history(self.site or "", b)
        return f, new

    def _spend(self) -> None:
        """사이트 전체 하루 한도와 이번 시간 몫(수집기 여럿이 함께 씀)."""
        if not SITE_DAY_MAX.get(self.site or ""):
            return
        f, b = self._load()
        # 수집기 여럿이 동시에 돌아도(매시 작업 + 5분마다 손님 요청) 법원 쪽에서 보면 간격이 지켜지게
        wait = self.gap - (time.time() - float(b.get("last_ts") or 0))
        if wait > 0:
            self._sleep(wait)
            f, b = self._load()
        cap = int(b["cap"])
        free = uncapped()
        if b["count"] >= cap and not free:
            raise DailyLimitReached(f"{self.site} 하루 전체 한도 {cap}번")
        hh = f"{now_kst():%H}"
        while not self.hourly and not free and b["hours"].get(hh, 0) >= HOUR_MAX_ALL:
            n = now_kst()
            left = 3600 - n.minute * 60 - n.second + 5
            print(
                f"   {self.site} 이번 시간 {HOUR_MAX_ALL}번 다 씀 — {left // 60}분 쉬고 이어서",
                flush=True,
            )
            self._sleep(left)
            f, b = self._load()
            hh = f"{now_kst():%H}"
        if self.hourly and not free and b["hours"].get(hh, 0) >= hour_share(cap):
            raise DailyLimitReached(
                f"{self.site} 이번 시간 몫 {hour_share(cap)}번 — 다음 시간에 이어서"
            )
        b["count"] += 1
        b["hours"][hh] = b["hours"].get(hh, 0) + 1
        by = b.setdefault("by", {})  # 11/23: 단계별 요청 수(날마다 history 에 남음)
        by[STEP] = by.get(STEP, 0) + 1
        b["last_ts"] = time.time()
        _save(f, b)

    def _shrink(self) -> int:
        """막힘 → 한도 20% 내리고 무사한 날 0부터(11/20 40% → 20%). 그날 센 수를 돌려줌."""
        if not SITE_DAY_MAX.get(self.site or ""):
            return 0
        f, b = self._load()
        b.update(cap=max(CAP_MIN, int(int(b["cap"]) * SHRINK)), ok_days=0, blocked=True,
                 blocks=int(b.get("blocks") or 0) + 1)  # fmt: skip
        _save(f, b)
        return int(b.get("count") or 0)

    def _run(self, fn: Callable[[], dict[str, Any]], what: str) -> dict[str, Any]:
        for n in range(1, FETCH_TRIES + 1):
            try:
                return fn()
            except Exception as e:  # noqa: BLE001 — 플레이라이트 오류는 모양이 여럿
                if n == FETCH_TRIES or "Failed to fetch" not in str(e):
                    raise
                print(
                    f"   {what} 연결 끊김 — {FETCH_WAIT_SEC * n:.0f}초 뒤 다시({n}/{FETCH_TRIES - 1})",
                    flush=True,
                )
                self._sleep(FETCH_WAIT_SEC * n)
                self._spend()
        raise AssertionError("닿지 않음")

    def call(self, fn: Callable[[], dict[str, Any]], what: str) -> dict[str, Any]:
        """fn 은 {"ok": bool, ...} 을 돌려주는 요청 한 번."""
        if self.daily_limit is not None and self.count >= self.daily_limit:
            raise DailyLimitReached(f"하루 한도 {self.daily_limit}건")
        if (
            self.step_max is not None and self.count >= self.step_max
        ):  # 매시 작업이 단계마다 나눠 준 몫
            raise DailyLimitReached(f"이 단계 몫 {self.step_max}번 — 다음 단계로")
        dl = os.environ.get("AUCS_DEADLINE")
        if dl and time.time() >= float(dl):  # 2번 PC: 다음 차례 전에 끝냄
            raise DailyLimitReached("이번 차례 시간 끝 — 다음 차례에 이어서")
        res: dict[str, Any] = {}
        for attempt in range(RETRIES):
            gap = self.gap + self._j(1.0) - (time.monotonic() - self._last)
            if gap > 0:
                self._sleep(gap)
            self._spend()
            res = self._run(fn, what)
            self._last = time.monotonic()
            self.count += 1
            if res.get("ok"):
                return res
            if "비정상" in str(res.get("msg", "")):  # 「비정상 IP」 — 다시 시도하지 않고 바로 멈춤
                break
            self._sleep(3.0 * (attempt + 1))
        if self.site:
            day_count = self._shrink()
            LOGS.mkdir(exist_ok=True)
            bf = _block_file(self.site)
            line = f"{now_kst():%Y-%m-%d %H:%M} {what} (그날 {day_count}번째에 막힘)\n"
            if bf.exists() and read_until(bf.read_text(encoding="utf-8")) is not None:
                # 오래 막힘 중의 확인도 막힘 → 하루 뒤에 다시 한 번만
                nxt = now_kst() + timedelta(hours=DAILY_CHECK_HOURS)
                line += f"until {nxt:%Y-%m-%d %H:%M}\n"
            bf.write_text(line, encoding="utf-8")
        raise Blocked(
            f"{what}: 응답 이상 (status {res.get('status')}) {str(res.get('msg', ''))[:120]}"
        )

    def between_cases(self) -> None:
        self._sleep(CASE_GAP_SEC + self._j(3.0))
