"""전국 실거래 지난 자료 받아 두기(11/21 대표님 「작업해」) → 대표님 PC 파일(DB 에 넣지 않음).

    uv run python -m aucs_workers.collectors.trades_archive --probe          # 2006-01 강남 아파트 한 달만 불러 봄
    uv run python -m aucs_workers.collectors.trades_archive                  # 매매 6종 · 전국 · 2006~올해 (이어 받기)
    uv run python -m aucs_workers.collectors.trades_archive --types apt_sale --from-year 2020

- 11/20 결정: 원본(수천만 줄)은 DB 밖 — D:\\Auction\\data\\실거래\\{종류}\\{연도}\\{시군구}.jsonl.gz
  (API 가 준 그대로 한 줄 = 거래 한 건, 「_ym」 만 덧붙임). DB 에는 나중에 요약만 올림.
- 공공데이터 운영계정(11/21): API 마다 하루 100만 번. 초당 제한은 정해진 값을 모름 → 기본 초당 5번(--rate).
- 이어 받기: 다 받은 (종류, 연도, 시군구) 파일이 있으면 건너뜀. 올해는 늘 다시 받음(신고가 아직 들어옴).
  연도 안 12달이 모두 받아져야 파일을 씀 — 중간에 멈추면 그 연도는 다음에 처음부터.
- 최근 연도부터 받음(2026 → 2006) — 중간에 멈춰도 쓸모 있는 자료가 먼저 쌓이게.
- 시군구 목록은 법정동코드 API(전국)에서 받아 sgg.json 에 둠(ref.regions 는 수도권만 — 화면 지역 목록에 쓰여 건드리지 않음).
"""

import argparse
import gzip
import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from functools import partial
from pathlib import Path
from typing import Any
from urllib.parse import unquote

import httpx
import xmltodict

from aucs_workers.collectors.regions import URL as REGION_URL
from aucs_workers.collectors.regions import rows_of
from aucs_workers.collectors.trades import BASE, TYPES, ApiError

SALES = [
    "apt_sale",
    "rowhouse_sale",
    "house_sale",
    "officetel_sale",
    "commercial_sale",
    "land_sale",
]
SIDO_ALL = [
    "서울특별시", "부산광역시", "대구광역시", "인천광역시", "광주광역시", "대전광역시", "울산광역시",
    "세종특별자치시", "경기도", "강원특별자치도", "충청북도", "충청남도", "전북특별자치도", "전라남도",
    "경상북도", "경상남도", "제주특별자치도",
]  # fmt: skip
ROOT = Path(os.getenv("TRADES_ARCHIVE") or Path(__file__).resolve().parents[5] / "data" / "실거래")
STOP_WORDS = ("LIMITED_NUMBER", "22 ", "SERVICE_KEY_IS_NOT_REGISTERED", "SERVICE ERROR")


class Limiter:
    """여러 줄기가 같이 불러도 초당 n번을 넘지 않게."""

    def __init__(self, per_sec: float) -> None:
        self.gap, self.next, self.lock = 1.0 / per_sec, 0.0, threading.Lock()

    def wait(self) -> None:
        with self.lock:
            now = time.monotonic()
            t = max(now, self.next)
            self.next = t + self.gap
        if t > now:
            time.sleep(t - now)


def service_key() -> str:
    key = os.getenv("DATA_GO_KR_SERVICE_KEY", "").strip().strip("\"'")
    key = unquote(key) if "%" in key else key
    if not key:
        raise SystemExit("DATA_GO_KR_SERVICE_KEY 가 비어 있습니다 (.env)")
    return key


def sgg_codes(client: httpx.Client, key: str) -> list[str]:
    """전국 시군구 코드 5자리(구가 있는 시는 구 단위). sgg.json 이 있으면 그것을 씀."""
    f = ROOT / "sgg.json"
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))["codes"]
    codes: dict[str, str] = {}
    for sido in SIDO_ALL:
        page = 1
        while True:
            res = client.get(REGION_URL, params={"ServiceKey": key, "type": "json", "pageNo": page,
                                                 "numOfRows": 1000, "flag": "Y", "locatadd_nm": sido})  # fmt: skip
            got = rows_of(res.json())
            for r in got:
                c = str(r.get("region_cd") or r.get("regionCd") or "")
                name = str(r.get("locatadd_nm") or r.get("locataddNm") or "")
                if len(c) == 10 and c[5:] == "00000" and c[2:5] != "000":
                    codes[c[:5]] = name
            if len(got) < 1000:
                break
            page += 1
    keep = sorted(
        c for c in codes if not (c.endswith("0") and any(o != c and o[:4] == c[:4] for o in codes))
    )  # 구가 있는 시는 구 단위로(trades.py 와 같은 규칙)
    ROOT.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps({"codes": keep, "names": {c: codes[c] for c in keep},
                             "fetched": date.today().isoformat()}, ensure_ascii=False, indent=1),
                 encoding="utf-8")  # fmt: skip
    return keep


def fetch_month(
    client: httpx.Client, lim: Limiter, key: str, svc: str, op: str, sgg: str, ym: str
) -> list[dict[str, Any]]:
    """한 달 · 한 시군구 전부(쪽 넘김). 잠깐 끊기면 세 번까지 다시."""
    items: list[dict[str, Any]] = []
    page = 1
    while True:
        for attempt in range(3):
            lim.wait()
            try:
                r = client.get(f"{BASE}/{svc}/{op}", params={"serviceKey": key, "LAWD_CD": sgg,
                               "DEAL_YMD": ym, "numOfRows": 1000, "pageNo": page})  # fmt: skip
                body = (r.text or "").strip()
                break
            except httpx.HTTPError:
                if attempt == 2:
                    raise
                time.sleep(3 * (attempt + 1))
        if not body or body.startswith(("Forbidden", "Unexpected", "API not found")):
            raise ApiError(body[:80] or "빈 응답")
        d = xmltodict.parse(body) if body.startswith("<") else json.loads(body)
        if "OpenAPI_ServiceResponse" in d:
            h = d["OpenAPI_ServiceResponse"].get("cmmMsgHeader", {})
            raise ApiError(
                f"{h.get('returnReasonCode')} {h.get('returnAuthMsg') or h.get('errMsg')}"
            )
        resp = d.get("response", {})
        if str(resp.get("header", {}).get("resultCode", "")) not in ("00", "000", "0"):
            raise ApiError(str(resp.get("header", {}).get("resultMsg")))
        b = resp.get("body") or {}
        part = (b.get("items") or {}).get("item") or []
        items += [{**x, "_ym": ym} for x in ([part] if isinstance(part, dict) else part)]
        if page * 1000 >= int(b.get("totalCount") or 0) or not part:
            return items
        page += 1


def say(msg: str) -> None:
    """화면에도, 파일(실거래\\archive.log)에도 — 창을 닫아도 어디서 멈췄는지 남게(11/21)."""
    print(msg, flush=True)
    ROOT.mkdir(parents=True, exist_ok=True)
    with open(ROOT / "archive.log", "a", encoding="utf-8") as f:
        f.write(f"{time.strftime('%m-%d %H:%M:%S')} {msg}\n")


def months(year: int, today: date) -> list[str]:
    last = today.month - 1 if year == today.year else 12  # 이번 달은 빼고(신고 중)
    return [f"{year}{m:02d}" for m in range(1, last + 1)]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--types", nargs="*", default=SALES)
    ap.add_argument("--from-year", type=int, default=2006)
    ap.add_argument("--to-year", type=int, default=date.today().year)
    ap.add_argument("--rate", type=float, default=5.0, help="초당 최대 호출(모르면 5)")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--probe", action="store_true", help="2006-01 강남구 아파트 매매 한 달만")
    a = ap.parse_args()
    key, today, lim = service_key(), date.today(), Limiter(a.rate)
    with httpx.Client(timeout=40) as client:
        if a.probe:
            svc, op, _, _ = TYPES["apt_sale"]
            for ym in ("200601", "201101", "202001"):
                got = fetch_month(client, lim, key, svc, op, "11680", ym)
                print(f"강남구 아파트 매매 {ym}: {len(got):,}건" + (f" · 예: {got[0].get('aptNm')} "
                      f"{got[0].get('dealAmount')}만" if got else ""))  # fmt: skip
            return
        sggs = sgg_codes(client, key)
        say(f"시작 · 시군구 {len(sggs)}곳 · 저장 {ROOT} · 초당 {a.rate}번")
        started, calls = time.monotonic(), 0
        with ThreadPoolExecutor(a.workers) as pool:
            for name in a.types:
                svc, op, _, _ = TYPES[name]
                for year in range(a.to_year, a.from_year - 1, -1):
                    yms = months(year, today)
                    if not yms:
                        continue
                    out_dir = ROOT / name / str(year)
                    out_dir.mkdir(parents=True, exist_ok=True)
                    n_year = 0
                    for sgg in sggs:
                        f = out_dir / f"{sgg}.jsonl.gz"
                        if f.exists() and year < today.year:
                            continue
                        try:
                            parts = list(
                                pool.map(partial(fetch_month, client, lim, key, svc, op, sgg), yms)
                            )
                        except ApiError as e:
                            if any(w in str(e) for w in STOP_WORDS):
                                say(f"[멈춤] {name} {year} {sgg}: {e} — 한도·키 확인")
                                raise SystemExit(1) from e
                            say(f"  ! {name} {year} {sgg}: {e} — 건너뜀(다음에 다시)")
                            continue
                        except Exception as e:  # noqa: BLE001 — 끊김 · 깨진 응답(XML) 등 무엇이든 그 칸만 건너뛰고 로그에 남김
                            # 11/21 04:45 인터넷이 끊겨(잠자기 등) 프로그램이 통째로 멈췄던 것 → 1분 쉬고 그 칸만 건너뜀
                            say(
                                f"  ! {name} {year} {sgg}: {type(e).__name__} {e} — 1분 쉬고 건너뜀"
                            )
                            time.sleep(60)
                            continue
                        calls += len(yms)
                        rows = [x for p in parts for x in p]
                        tmp = f.with_suffix(".tmp")
                        with gzip.open(tmp, "wt", encoding="utf-8") as g:
                            for x in rows:
                                g.write(json.dumps(x, ensure_ascii=False) + "\n")
                        tmp.replace(
                            f
                        )  # 다 쓴 뒤에 이름을 바꿈 — 중간에 꺼져도 반쪽 파일이 남지 않게
                        n_year += len(rows)
                    mins = (time.monotonic() - started) / 60
                    say(f"{name} {year}: {n_year:,}건 · 지금까지 약 {calls:,}번 · {mins:.0f}분")


if __name__ == "__main__":
    main()
