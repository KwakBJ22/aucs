"""전국 매각결과 · 물건 목록 보관(11/18 대표님 — 시간이 지나면 다시 못 받는 것만 지금부터 전국으로).

- 법원 사이트는 매각결과를 최근 1주만 보여 주고, 물건은 매각되면 목록에서 빠짐 → 날마다 받아 둠.
- 서비스 지역(수도권 16곳, aucs_rules/courts.py)은 아침 묶음이 따로 받으므로 여기서는 그 밖의 법원만.
- 원문 보관 표(raw.court_result_raw · raw.court_item_raw)에만 넣음 — 화면 · 통계 표(core)에는 넣지 않음.
  지역을 열 때 원문에서 다시 꺼내 채움.
- 법원 코드는 사이트의 법원사무소 목록(selectCortOfcCdLst)에서 받고 logs/court_codes.json 에 남김.
  못 받으면 남겨 둔 목록을 씀. 그것도 없으면 멈춤.
- 요청 간격 · 하루 한도는 다른 법원 수집과 같은 규칙(polite.py)을 함께 씀.

    uv run python -m aucs_workers.collectors.court_nationwide
    uv run python -m aucs_workers.collectors.court_nationwide --codes   # 법원 목록만 받아 남김
"""

import argparse
import json
import re
from collections.abc import Iterator
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from aucs_rules.courts import COURTS

from aucs_workers.collectors.browser import launch_chrome
from aucs_workers.collectors.court_site import (
    JS_ITEMS,
    JS_RESULTS,
    PAGE_SIZE,
    RESULT_PAGE,
    SEARCH_PAGE,
)
from aucs_workers.collectors.polite import Polite
from aucs_workers.collectors.store import save_raw
from aucs_workers.db import connect
from aucs_workers.jobs.runlog import run

CODES_FILE = Path(__file__).resolve().parents[4] / "logs" / "court_codes.json"
CODE_RE = re.compile(r"^B\d{6}$")
MIN_COURTS = 30  # 전국 법원이 이보다 적게 잡히면 목록을 잘못 읽은 것으로 봄

JS_CODES = r"""
async () => {
  const r = await fetch('/pgj/pgjComm/selectCortOfcCdLst.on', { method: 'POST',
    headers: { 'Content-Type': 'application/json;charset=UTF-8', 'Accept': 'application/json' },
    body: '{}', credentials: 'include' });
  const text = await r.text();
  return { ok: r.ok, status: r.status, text: text };
}"""


def find_courts(data: Any) -> dict[str, str]:
    """응답 JSON 어디에 있든 「B + 숫자 6자리」 코드와 법원 이름이 같이 든 줄을 모음(순수 함수)."""
    out: dict[str, str] = {}

    def walk(x: Any) -> None:
        if isinstance(x, dict):
            code = next(
                (v for v in x.values() if isinstance(v, str) and CODE_RE.match(v.strip())), None
            )
            names = [
                v.strip()
                for v in x.values()
                if isinstance(v, str) and ("법원" in v or "지원" in v) and not CODE_RE.match(v)
            ]
            if code and names:
                out[code.strip()] = min(names, key=len)
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)

    walk(data)
    return out


def load_codes() -> dict[str, str]:
    try:
        return dict(json.loads(CODES_FILE.read_text(encoding="utf-8")))
    except Exception:  # noqa: BLE001
        return {}


def fetch_codes(page: Any, polite: Polite) -> dict[str, str]:
    """사이트에서 법원 목록을 받아 파일에 남김. 못 읽으면 남겨 둔 목록."""
    try:
        res = polite.call(lambda: dict(page.evaluate(JS_CODES)), "법원 목록")
        got = find_courts(json.loads(res["text"]))
    except Exception as e:  # noqa: BLE001 — 막힘(Blocked)은 위로
        if type(e).__name__ in ("Blocked", "DailyLimitReached"):
            raise
        print(f"   법원 목록을 못 읽음({type(e).__name__}: {str(e)[:120]}) — 남겨 둔 목록을 씀")
        got = {}
    if len(got) >= MIN_COURTS:
        CODES_FILE.parent.mkdir(exist_ok=True)
        CODES_FILE.write_text(json.dumps(got, ensure_ascii=False, indent=1), encoding="utf-8")
        return got
    if got:
        print(f"   법원 목록이 {len(got)}곳뿐 — 이상해서 남겨 둔 목록을 씀")
    return load_codes()


def pages(
    page: Any, polite: Polite, courts: dict[str, str], *, results: bool, d_from: str, d_to: str
) -> Iterator[tuple[str, list[dict[str, Any]]]]:
    """court_site.fetch_pages 와 같은 요청 — 브라우저 하나로 법원 목록 · 물건 · 결과를 이어 받으려고 따로 둠."""
    for cd, name in courts.items():
        pg, got = 1, 0
        while True:

            def one(cd: str = cd, pg: int = pg) -> dict[str, Any]:
                if results:
                    return dict(page.evaluate(JS_RESULTS, [cd, pg, PAGE_SIZE]))
                return dict(page.evaluate(JS_ITEMS, [cd, pg, PAGE_SIZE, d_from, d_to]))

            res = polite.call(one, f"{name} {pg}쪽")  # 연결 끊김 다시 시도는 polite 가 함
            rows: list[dict[str, Any]] = res["rows"]
            yield cd, rows
            got += len(rows)
            if not rows or got >= int(res["total"]):
                break
            pg += 1
        polite.between_cases()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--codes", action="store_true", help="법원 목록만 받아 logs/court_codes.json 에"
    )
    ap.add_argument("--weeks", type=int, default=6)
    ap.add_argument("--show", action="store_true")
    a = ap.parse_args()
    from playwright.sync_api import sync_playwright

    polite = Polite(hourly=False)
    d0 = date.today()
    d_from, d_to = f"{d0:%Y%m%d}", f"{d0 + timedelta(weeks=a.weeks):%Y%m%d}"
    with connect() as conn, run(conn, "court_nationwide", "전국 매각결과 · 물건 목록 보관") as job:
        with sync_playwright() as p:
            browser = launch_chrome(p, headless=not a.show)
            page = browser.new_page()
            try:
                # 매각결과가 먼저 — 사이트가 최근 1주만 보여 줘서 하루 한도에 걸려도 이것부터
                page.goto(RESULT_PAGE, wait_until="networkidle", timeout=60000)
                codes = fetch_codes(page, polite)
                others = {cd: nm for cd, nm in codes.items() if cd not in COURTS}
                print(f"   전국 {len(codes)}곳 · 수도권 밖 {len(others)}곳", flush=True)
                if a.codes:
                    return
                if not others:
                    raise SystemExit("법원 목록이 없음 — 멈춤")
                n_items = n_results = 0
                for cd, rows in pages(page, polite, others, results=True, d_from="", d_to=""):
                    n_results += save_raw(conn, "court_result_raw", cd, rows)
                    conn.commit()
                print(f"   매각결과 새 줄 {n_results:,}", flush=True)
                page.goto(SEARCH_PAGE, wait_until="networkidle", timeout=60000)
                for cd, rows in pages(
                    page, polite, others, results=False, d_from=d_from, d_to=d_to
                ):
                    n_items += save_raw(conn, "court_item_raw", cd, rows)
                    conn.commit()
                print(f"   물건 목록 새 줄 {n_items:,}", flush=True)
                job.count = n_items + n_results
            finally:
                browser.close()
    print(f"끝: 새로 보관 {job.count:,}줄")


if __name__ == "__main__":
    main()
