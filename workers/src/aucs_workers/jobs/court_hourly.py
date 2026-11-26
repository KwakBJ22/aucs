"""법원 수집 매시(11/4 저녁 대표님 — 하루 종일 나눠 계속 받기, PC 는 웬만하면 켜 둠).

작업 스케줄러가 매시 10분에 부르고, PC 가 꺼져 있다 켜지면 바로 한 번 돕니다(StartWhenAvailable).
법원 서비스 시간(06~24시)에만 돌고, 시간마다 몫(하루 한도 ÷ 18, polite.py)을 다 쓰면 그 단계는 멈추고 다음 시간에 이어 받습니다.
받는 순서(손님 눈에 먼저 띄는 것부터): 관심 물건 → 입찰 7일 안 빈 서류(11/24) → 새 사건 물건상세(11/18) → 홈에 뜰 물건 사진(물건상세만, 11/7)
→ 다음 회차 미리 → 물건상세 첫 바퀴 → 서류 보관 → 분석.
앞 차례가 아직 돌고 있으면(70분 안) 겹쳐 띄우지 않습니다.

    uv run python -m aucs_workers.jobs.court_hourly
"""

import os
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

from aucs_workers.collectors.polite import SITE_DAY_MAX, Polite, hour_share

LOCK = Path(__file__).resolve().parents[4] / "logs" / "court_hourly.lock"
SERVICE = range(6, 24)  # 법원 06:00~24:00 (00~01시도 열리지만 하루 몫을 나누는 18시간에 맞춤)
# (이름, 명령, 시간 몫 가운데 이 단계 몫 %) — 11/5: 앞 단계가 몫을 다 써서 서류 보관·다음 회차가 한 번도 못 돌았음
STEPS = [
    ("관심 물건 서류", ["aucs_workers.collectors.court_docs", "--watched"], None),
    # 11/24 대표님(2024타경57221): 입찰 7일 안인데 물건상세 · 문건송달 · 현황조사가 빈 사건 742건 → 관심 물건 바로 다음에 25%.
    #   새 사건 40 → 30, 사진 20 → 15, 첫 바퀴 15 → 10, 서류 보관 15 → 10. 받을 것이 없으면 그 몫은 서류 보관으로
    ("입찰 임박 서류", ["aucs_workers.collectors.court_docs", "--soon"], 25),
    # 11/18: 새 사건이 첫 바퀴(입찰 가까운 순)에서 밀려 며칠씩 사진·명세서가 비었음 → 맨 앞에 40%.
    #   사진 30 → 20, 다음 회차 15 → 10, 첫 바퀴 35 → 15, 서류 보관 20 → 15. 새 사건이 없으면 그 몫은 첫 바퀴로
    # 11/24 밤 대표님: 서류 보관(현황조사서)이 하루 489번뿐 → 입찰 7일 안 84% · 8~14일 19% 로 떨어짐. 새 사건 30 → 25, 보관 10 → 15
    ("새 사건 물건상세", ["aucs_workers.collectors.court_docs", "--new"], 25),
    # 11/7: 홈은 사진 있는 물건만 띄움 → 홈에 뜰 물건 사진을 가장 크게(물건상세 한 번이라 같은 몫으로 5배쯤)
    # 11/7 오전: 물건상세 첫 바퀴(모든 진행 물건, 약 9,700번 · 일주일 남짓) — 서류 보관 35 → 20, 사진 35 → 30, 다음 회차 20 → 15
    ("홈에 뜰 물건 사진", ["aucs_workers.collectors.court_docs", "--picks"], 15),
    ("다음 회차 미리 받기", ["aucs_workers.collectors.court_docs", "--next"], 10),
    ("물건상세 첫 바퀴", ["aucs_workers.collectors.court_docs", "--details"], 10),
    ("서류 보관", ["aucs_workers.collectors.court_docs", "--archive"], 15),
    # 11/7 대표님: 당분간 이 노트북에서 감정평가서 원본(KAPA)을 받지 않음 — KAPA 가 자동 조회로 막음. 몫 10% 는 첫 바퀴로
    ("분석(새 서류)", ["aucs_workers.jobs.analyze", "--stale"], None),
]


def _cap() -> int:
    """오늘 법원 하루 한도(저절로 바뀐 값)."""
    try:
        return int(Polite(site="court", jitter=False)._load()[1]["cap"])
    except Exception:  # noqa: BLE001 — 막힘 표시 중이면 시작 한도로
        return SITE_DAY_MAX["court"]


def _new_left() -> bool:
    """새 사건 물건상세로 받을 사건이 남았나(11/18)."""
    try:
        from datetime import date

        from aucs_workers.collectors.court_docs import new_targets
        from aucs_workers.db import connect

        with connect() as conn:
            return bool(new_targets(conn, date.today()))
    except Exception:  # noqa: BLE001 — 모르면 몫을 옮기지 않음
        return True


def _soon_left() -> bool:
    """입찰 임박 서류로 받을 사건이 남았나(11/24)."""
    try:
        from datetime import date

        from aucs_workers.collectors.court_docs import soon_targets
        from aucs_workers.db import connect

        with connect() as conn:
            return bool(soon_targets(conn, date.today()))
    except Exception:  # noqa: BLE001 — 모르면 몫을 옮기지 않음
        return True


def _details_left() -> bool:
    """물건상세 첫 바퀴로 받을 사건이 아직 남았나."""
    try:
        from datetime import date

        from aucs_workers.collectors.court_docs import details_targets
        from aucs_workers.db import connect

        with connect() as conn:
            return bool(details_targets(conn, date.today()))
    except Exception:  # noqa: BLE001 — 모르면 지금처럼(몫을 옮기지 않음)
        return True


# 11/18~11/24 저녁 목록 시험(20 · 21 · 22 · 23시): 네 번 모두 그 시각 새 사건 0건, 다음 날 06시에 145~288건
#   → 법원은 닫혀 있는 00~06시 사이에 올림. 저녁 「새 물건 채우기」는 만들지 않고 시험 코드는 걷어 냄(11/25 대표님)


def alive(pid: int) -> bool:
    """그 프로세스가 아직 살아 있나. 윈도우에서 os.kill(pid, 0)은 프로세스를 끝내 버리므로 쓰지 않음."""
    if pid <= 0:
        return False
    if os.name != "nt":
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True
    import ctypes

    k32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
    h = k32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return False
    try:
        code = ctypes.c_ulong()
        ok = bool(k32.GetExitCodeProcess(h, ctypes.byref(code)))
        return ok and code.value == 259  # STILL_ACTIVE
    finally:
        k32.CloseHandle(h)


def busy() -> bool:
    """앞 차례가 70분 안에 시작해 아직 안 끝났으면 True.

    11/22: 09:10 차례가 09:28 에 끊겼는데 잠금 파일이 남아 10:10 차례가 건너뜀 →
    잠금에 적힌 프로세스가 이미 없으면 기다리지 않고 바로 돎."""
    if not LOCK.exists() or time.time() - LOCK.stat().st_mtime >= 70 * 60:
        return False
    try:
        pid = int(LOCK.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return True  # 읽는 찰나 · 이상한 내용이면 예전처럼 기다림
    if alive(pid):
        return True
    print(f"앞 차례(프로세스 {pid})가 이미 끝나 있음 — 잠금을 지우고 돎", flush=True)
    return False


# 11/23 대표님: 전국 보관을 아침 묶음에서 빼 오후로 — 14시 뒤 첫 매시 차례가 하루 한 번, 그 시간은 다른 단계를 쉼(천천히 약 70분)
NATIONWIDE_FROM = 14
NATIONWIDE_DONE = LOCK.parent / "court_nationwide.done"


# 11/26 밤 대표님: 전국 보관을 멈춤 — 법원에 막힌 세 번(11/23 · 11/26 2번 PC 14:10 · 1번 PC 19:34)이 모두 전국 보관 중이었음.
#   다시 할 때는 하루 몇십 쪽씩 아주 천천히 따로 시험한 뒤 켬.
NATIONWIDE_ON = False


def nationwide_due(now: datetime) -> bool:
    if not NATIONWIDE_ON or now.hour < NATIONWIDE_FROM:
        return False
    try:
        return NATIONWIDE_DONE.read_text(encoding="utf-8").strip() != now.date().isoformat()
    except OSError:
        return True


# 11/25 대표님: 공시가격(브이월드)이 아침마다 응답이 늦어 사흘 연속 실패 → 아침 묶음에서 빼 15시 뒤 첫 매시 차례 끝에 하루 한 번.
#   법원에 묻지 않으므로 법원 몫과 상관없음.
OFFICIAL_FROM = 15
OFFICIAL_DONE = LOCK.parent / "official_prices.done"


def official_due(now: datetime) -> bool:
    if now.hour < OFFICIAL_FROM:
        return False
    try:
        return OFFICIAL_DONE.read_text(encoding="utf-8").strip() != now.date().isoformat()
    except OSError:
        return True


# 11/26 대표님: PC 두 대(다른 인터넷)로 나눠 받기 — .env 의 AUCS_ROLE 로 맡을 일을 나눔. 하루 법원 한도는 PC 마다 따로(logs/court_budget.json).
#   main(1번 PC): 아침 묶음 · 매시(관심 · 입찰 임박 · 새 사건 · 사진 · 다음 회차 · 첫 바퀴 · 분석) · 공시가격 · 관리자 요청
#   docs(2번 PC): 매시 서류 보관(현황조사서 · 문건송달)만 몫 전부로 + 14시 뒤 전국 보관. 분석은 1번 PC 가 다음 차례에
#   11/26 저녁 대표님: 2번 PC 가 꺼져도 1번 PC 는 대신하지 않음(각자 따로) — 19:34 1번 PC 가 대신 돌다 막혔음.
#   서류 보관 · 전국 보관은 2번 PC 몫: 꺼져 있는 동안은 쉬고, 켜지면 멈춘 곳부터. docs_pc 기록은 살아 있는지 보는 용도로만.
DOCS_ALIVE_MIN = 90


def role() -> str:
    import aucs_workers.db  # noqa: F401 — .env 를 읽음

    return (os.environ.get("AUCS_ROLE") or "main").strip().lower()


def docs_pc_alive() -> bool:
    try:
        from aucs_workers.db import connect

        with connect() as conn:
            return bool(conn.execute(
                "select 1 from ops.job_runs where job_id = 'docs_pc' and started_at > now() - %s * interval '1 minute' limit 1",
                (DOCS_ALIVE_MIN,),
            ).fetchone())  # fmt: skip
    except Exception:  # noqa: BLE001 — 모르면 1번 PC 가 대신 함(빠지는 것보다 겹치는 편이 나음)
        return False


def heartbeat() -> None:
    try:
        from aucs_workers.db import connect
        from aucs_workers.jobs.runlog import run

        with connect() as conn, run(conn, "docs_pc", "2번 PC(서류 보관) 살아 있음"):
            pass
    except Exception as e:  # noqa: BLE001
        print(f"   살아 있음 기록 못 함({type(e).__name__})", flush=True)


def run_nationwide() -> None:
    print("── 전국 매각결과 · 물건 목록 보관(하루 한 번, 다른 단계 쉼)", flush=True)
    NATIONWIDE_DONE.write_text(datetime.now().date().isoformat(), encoding="utf-8")
    code = subprocess.call([sys.executable, "-m", "aucs_workers.collectors.court_nationwide"])
    if code != 0:
        print(f"   전국 보관 멈춤({code}) — 내일 다시", flush=True)


def docs_main() -> None:
    """2번 PC: 명세서 원본(입찰 7일 안) → 서류 보관."""
    heartbeat()
    if nationwide_due(datetime.now()):
        run_nationwide()
        return
    # 11/26 대표님: 2번 PC 는 한도 · 시간 몫 없이 계속(polite.uncapped) — 다음 차례(매시 10분) 2분 전까지만
    end = datetime.now().replace(minute=0, second=0, microsecond=0) + timedelta(hours=1, minutes=8)
    # 11/26 밤 지시 1126a: 입찰 7일 안 매각물건명세서 원본 먼저 — 한 차례 최대 25분, 남는 시간은 서류 보관
    print("── 명세서 원본(2번 PC)", flush=True)
    spec_end = min(end, datetime.now() + timedelta(minutes=25))
    env = dict(os.environ, AUCS_DEADLINE=str(spec_end.timestamp()))
    code = subprocess.call([sys.executable, "-m", "aucs_workers.collectors.court_spec"], env=env)
    if code != 0:
        print(f"   명세서 원본 멈춤({code}) — 다음 차례에 이어서", flush=True)
    print("── 서류 보관(2번 PC)", flush=True)
    env = dict(os.environ, AUCS_DEADLINE=str(end.timestamp()))
    cmd = [sys.executable, "-m", "aucs_workers.collectors.court_docs", "--archive"]
    code = subprocess.call(cmd, env=env)
    if code != 0:
        print(f"   서류 보관 멈춤({code}) — 한도·막힘이면 다음 시간에 이어서", flush=True)


def main() -> None:
    if datetime.now().hour not in SERVICE:
        print("법원 서비스 시간이 아니에요 — 쉼")
        return
    if busy():
        print("앞 차례가 아직 도는 중 — 겹쳐 띄우지 않음")
        return
    LOCK.parent.mkdir(exist_ok=True)
    LOCK.write_text(str(os.getpid()), encoding="utf-8")
    try:
        if role() == "docs":
            docs_main()
            return
        print("서류 보관 · 전국 보관은 2번 PC 몫 — 건너뜀", flush=True)
        share = hour_share(_cap())
        # 11/18: 새 사건이 없으면 그 몫(40)을 첫 바퀴로 → 첫 바퀴도 끝났으면 둘 다 서류 보관(현황조사서)으로(11/12)
        new_spare = 0 if _new_left() else 25
        soon_spare = 0 if _soon_left() else 25
        details_left = _details_left()
        for name, mod, pct in STEPS:
            if name == "서류 보관":
                continue
            if name == "새 사건 물건상세" and new_spare:
                continue
            if name == "입찰 임박 서류" and soon_spare:
                continue
            if pct and name == "서류 보관":
                pct += soon_spare
            if pct and name == "물건상세 첫 바퀴":
                if not details_left:
                    continue
                pct += new_spare
            if pct and name == "서류 보관" and not details_left:
                pct += 10 + new_spare
            print(f"── {name}", flush=True)
            env = dict(os.environ)
            if pct:
                env["AUCS_STEP_REQ"] = str(
                    max(7, share * pct // 100)
                )  # 사건 하나는 끝낼 만큼(6~7번)
            code = subprocess.call([sys.executable, "-m", *mod], env=env)
            if code != 0:
                print(f"   {name} 멈춤({code}) — 한도·막힘이면 다음 시간에 이어서", flush=True)
        if official_due(datetime.now()):
            print("── 공시가격(하루 한 번, 브이월드)", flush=True)
            OFFICIAL_DONE.write_text(datetime.now().date().isoformat(), encoding="utf-8")
            cmd = [sys.executable, "-m", "aucs_workers.collectors.official_prices", "--cap", "1500"]
            if subprocess.call(cmd) != 0:
                print("   공시가격 멈춤 — 내일 다시", flush=True)
    finally:
        LOCK.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
