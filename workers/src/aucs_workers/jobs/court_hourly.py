"""법원 수집 매시(11/4 저녁 대표님 — 하루 종일 나눠 계속 받기, PC 는 웬만하면 켜 둠).

작업 스케줄러가 매시 10분에 부르고, PC 가 꺼져 있다 켜지면 바로 한 번 돕니다(StartWhenAvailable).
법원 서비스 시간(06~24시)에만 돌고, 시간마다 몫(하루 한도 ÷ 18, polite.py)을 다 쓰면 그 단계는 멈추고 다음 시간에 이어 받습니다.
받는 순서(손님 눈에 먼저 띄는 것부터): 관심 물건 → 새 사건 물건상세(11/18) → 홈에 뜰 물건 사진(물건상세만, 11/7)
→ 다음 회차 미리 → 물건상세 첫 바퀴 → 서류 보관 → 분석.
앞 차례가 아직 돌고 있으면(70분 안) 겹쳐 띄우지 않습니다.

    uv run python -m aucs_workers.jobs.court_hourly
"""

import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from aucs_workers.collectors.polite import SITE_DAY_MAX, Polite, hour_share

LOCK = Path(__file__).resolve().parents[4] / "logs" / "court_hourly.lock"
SERVICE = range(6, 24)  # 법원 06:00~24:00 (00~01시도 열리지만 하루 몫을 나누는 18시간에 맞춤)
# (이름, 명령, 시간 몫 가운데 이 단계 몫 %) — 11/5: 앞 단계가 몫을 다 써서 서류 보관·다음 회차가 한 번도 못 돌았음
STEPS = [
    ("관심 물건 서류", ["aucs_workers.collectors.court_docs", "--watched"], None),
    # 11/18: 새 사건이 첫 바퀴(입찰 가까운 순)에서 밀려 며칠씩 사진·명세서가 비었음 → 맨 앞에 40%.
    #   사진 30 → 20, 다음 회차 15 → 10, 첫 바퀴 35 → 15, 서류 보관 20 → 15. 새 사건이 없으면 그 몫은 첫 바퀴로
    ("새 사건 물건상세", ["aucs_workers.collectors.court_docs", "--new"], 40),
    # 11/7: 홈은 사진 있는 물건만 띄움 → 홈에 뜰 물건 사진을 가장 크게(물건상세 한 번이라 같은 몫으로 5배쯤)
    # 11/7 오전: 물건상세 첫 바퀴(모든 진행 물건, 약 9,700번 · 일주일 남짓) — 서류 보관 35 → 20, 사진 35 → 30, 다음 회차 20 → 15
    ("홈에 뜰 물건 사진", ["aucs_workers.collectors.court_docs", "--picks"], 20),
    ("다음 회차 미리 받기", ["aucs_workers.collectors.court_docs", "--next"], 10),
    ("물건상세 첫 바퀴", ["aucs_workers.collectors.court_docs", "--details"], 15),
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


# 11/18 대표님: 법원이 그날 물건을 몇 시까지 다 올리는지 재기 — 저녁에 법원 목록을 한 번 더 받고,
#   다음 날 06:00 아침 묶음에서 새 사건이 더 나오는지 센다. 하루씩 한 시간 당김(토·일은 법원이 안 올림).
#   안전한 시각이 정해지면 그 시각~24시를 새 물건 채우기로 바꿈. 아침 06:00 묶음은 그대로.
# 11/18 20시는 하루 한도가 먼저 다 차서 못 잼 → 11/19 20시로 다시(대표님)
# 11/20 대표님: 11/19 20시 시험에서 새 사건 0건인데 다음 날 06시에 288건 → 20시엔 아직 안 올라옴. 한 시간씩 늦춤
EVENING_PROBE = {"2026-11-19": 20, "2026-11-20": 21, "2026-11-23": 22, "2026-11-24": 23}
PROBE_RESERVE = 450  # 저녁 목록 한 번(수도권 약 330쪽) 몫 — 시험 날엔 그 시각 전까지 매시 수집이 이만큼 남겨 둠



def probe_reserved() -> bool:
    """오늘 시험이 아직 남았고, 이번 시간 몫까지 쓰면 남은 몫이 시험 몫 아래가 되면 True(이번 시간 매시 수집은 쉼).

    11/19: 처음엔 「지금 남은 몫 < 450」만 봐서 18시에 482가 남은 채 돌고 200번을 써 20시 시험에 282번만 남았음
    → 이번 시간 몫(hour_share)을 쓴 뒤 기준으로 봄."""
    h = EVENING_PROBE.get(datetime.now().date().isoformat())
    if h is None or datetime.now().hour >= h:
        return False
    try:
        b = Polite(site="court", jitter=False)._load()[1]
        cap = int(b["cap"])
        return cap - int(b["count"]) - hour_share(cap) < PROBE_RESERVE
    except Exception:  # noqa: BLE001 — 모르면 지금처럼
        return False


def evening_probe() -> None:
    """오늘 정한 시각이면 법원 목록을 한 번 받음(아침 물건 수집과 같은 명령)."""
    now = datetime.now()
    if EVENING_PROBE.get(now.date().isoformat()) != now.hour:
        return
    print(f"── 저녁 목록 시험({now.hour}시)", flush=True)
    code = subprocess.call([sys.executable, "-m", "aucs_workers.collectors.court_items"])
    if code != 0:
        print(f"   저녁 목록 시험 멈춤({code})", flush=True)


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


def nationwide_due(now: datetime) -> bool:
    if now.hour < NATIONWIDE_FROM:
        return False
    try:
        return NATIONWIDE_DONE.read_text(encoding="utf-8").strip() != now.date().isoformat()
    except OSError:
        return True


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
        evening_probe()
        if probe_reserved():
            print(f"저녁 목록 시험 몫({PROBE_RESERVE}번)을 남겨 두려고 이번 시간은 쉼", flush=True)
            return
        if nationwide_due(datetime.now()):
            print("── 전국 매각결과 · 물건 목록 보관(하루 한 번, 다른 단계 쉼)", flush=True)
            NATIONWIDE_DONE.write_text(datetime.now().date().isoformat(), encoding="utf-8")
            cmd = [sys.executable, "-m", "aucs_workers.collectors.court_nationwide"]
            code = subprocess.call(cmd)
            if code != 0:
                print(f"   전국 보관 멈춤({code}) — 내일 다시", flush=True)
            return
        share = hour_share(_cap())
        # 11/18: 새 사건이 없으면 그 몫(40)을 첫 바퀴로 → 첫 바퀴도 끝났으면 둘 다 서류 보관(현황조사서)으로(11/12)
        new_spare = 0 if _new_left() else 40
        details_left = _details_left()
        for name, mod, pct in STEPS:
            if name == "새 사건 물건상세" and new_spare:
                continue
            if pct and name == "물건상세 첫 바퀴":
                if not details_left:
                    continue
                pct += new_spare
            if pct and name == "서류 보관" and not details_left:
                pct += 15 + new_spare
            print(f"── {name}", flush=True)
            env = dict(os.environ)
            if pct:
                env["AUCS_STEP_REQ"] = str(
                    max(7, share * pct // 100)
                )  # 사건 하나는 끝낼 만큼(6~7번)
            code = subprocess.call([sys.executable, "-m", *mod], env=env)
            if code != 0:
                print(f"   {name} 멈춤({code}) — 한도·막힘이면 다음 시간에 이어서", flush=True)
    finally:
        LOCK.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
