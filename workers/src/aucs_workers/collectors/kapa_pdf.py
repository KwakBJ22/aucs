"""감정평가서 원본 받기 (11/4 대표님 — 한국감정평가사협회 사용 허락, 법원 「감정평가서 보기」와 같은 길).

법원 물건상세의 「감정평가서 보기」는 KAPA 주소
    https://ca.kapanet.or.kr/view/{법원코드 숫자}/{사건번호}/{명령횟차}/{감정서 번호}/{작성일}
를 엽니다. 감정서 번호는 court_docs 가 받은 raw 'appraisal' 에 있습니다.
받은 PDF 는 저장하지 않고 회사 이름 · 쪽수 · 앞부분 글만 raw 'appraisal_pdf' 에 남깁니다.

    uv run python -m aucs_workers.collectors.kapa_pdf            # 진행 물건 중 아직 안 받은 것(하루 한도)
    uv run python -m aucs_workers.collectors.kapa_pdf --probe    # 한 건만 — 어떻게 열리는지 logs/kapa_probe.txt 에 적음
"""

import argparse
import re
from datetime import date
from pathlib import Path
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from aucs_workers.collectors.browser import launch_chrome
from aucs_workers.collectors.parse import checksum
from aucs_workers.collectors.polite import DailyLimitReached, Polite
from aucs_workers.db import connect
from aucs_workers.extract.appraisal_pdf import read_pdf
from aucs_workers.jobs.runlog import run

DAY_MAX = 150  # 하루 원본 수(입찰 가까운 순)
COURT_REFERER = "https://www.courtauction.go.kr/"
BASE = "https://ca.kapanet.or.kr"
PROBE_LOG = Path(__file__).resolve().parents[4] / "logs" / "kapa_probe.txt"


def view_url(info: dict[str, Any]) -> str | None:
    """raw 'appraisal' 의 info → KAPA 열람 주소(법원 팝업 PGJ15BP03 과 같은 꼴)."""
    need = ("cortOfcCd", "csNo", "ordTsCnt", "aeeWevlNo", "wrtYmd")
    if not all(info.get(k) for k in need):
        return None
    court = str(info["cortOfcCd"]).replace("B", "")
    return f"{BASE}/view/{court}/{info['csNo']}/{info['ordTsCnt']}/{info['aeeWevlNo']}/{info['wrtYmd']}"


def targets(conn: psycopg.Connection, today: date, limit: int) -> list[tuple[str, dict[str, Any]]]:
    """감정서 번호가 있고 원본을 아직 안 받은 진행 사건 — 입찰 가까운 순."""
    rows = conn.execute(
        """select a.case_id, a.payload -> 'info' as info
           from (select distinct on (case_id) case_id, payload from raw.court_doc_raw
                 where doc_kind = 'appraisal' order by case_id, fetched_at desc) a
           join lateral (select min(sale_date) as d from core.items i where i.case_id = a.case_id
                         and i.sale_date >= %s) s on s.d is not null
           where a.payload -> 'info' ->> 'aeeWevlNo' is not null
             and not exists (select 1 from raw.court_doc_raw p where p.case_id = a.case_id and p.doc_kind = 'appraisal_pdf'
                             and p.payload ->> 'no' = a.payload -> 'info' ->> 'aeeWevlNo')
           order by s.d limit %s""",
        (today, limit),
    ).fetchall()
    return [(r[0], dict(r[1])) for r in rows]


_SRC = re.compile(r"""(?:src|href|location(?:\.href)?)\s*=\s*["']([^"']+)["']""", re.I)


def fetch_pdf(ctx: Any, page: Any, url: str, probe: list[str] | None = None) -> bytes | None:
    """열람 주소 → PDF 바이트. ① 바로 PDF ② 페이지 안 iframe·주소 ③ 브라우저로 열어 내려받기 — 차례로."""
    r = ctx.request.get(url, headers={"Referer": COURT_REFERER}, timeout=60000)
    body = r.body()
    if probe is not None:
        probe.append(f"① {r.status} {r.headers.get('content-type')} {len(body)}B")
    if body[:4] == b"%PDF":
        return bytes(body)
    html = body.decode("euc-kr", "ignore")
    if probe is not None:
        probe.append(html[:3000])
    for src in _SRC.findall(html):
        if not src or src.startswith(
            ("http://get.adobe", "https://get.adobe", "/js-css", "/lib", "/image", "#")
        ):
            continue
        full = (
            src if src.startswith("http") else f"{BASE}{src if src.startswith('/') else '/' + src}"
        )
        r2 = ctx.request.get(full, headers={"Referer": url}, timeout=120000)
        b2 = r2.body()
        if probe is not None:
            probe.append(f"② {full[:120]} {r2.status} {r2.headers.get('content-type')} {len(b2)}B")
        if b2[:4] == b"%PDF":
            return bytes(b2)
    # ③ 화면처럼 열기 — 스크립트가 iframe 주소를 채우거나 내려받기로 줄 때
    got: list[bytes] = []

    def on_response(resp: Any) -> None:
        try:
            if "pdf" in (resp.headers.get("content-type") or "").lower():
                got.append(resp.body())
        except Exception:  # noqa: BLE001
            pass

    page.on("response", on_response)
    try:
        with page.expect_download(timeout=30000) as dl:
            try:
                page.goto(url, referer=COURT_REFERER, timeout=60000)
            except Exception:  # noqa: BLE001 — 내려받기로 시작하면 goto 가 오류를 냄
                pass
        path = dl.value.path()
        if path:
            got.append(Path(path).read_bytes())
    except Exception as e:  # noqa: BLE001
        if probe is not None:
            probe.append(f"③ 내려받기 없음 {type(e).__name__}")
    finally:
        page.remove_listener("response", on_response)
    pdf = next((b for b in got if b[:4] == b"%PDF"), None)
    if probe is not None:
        probe.append(f"③ {'PDF ' + str(len(pdf)) + 'B' if pdf else '못 받음'}")
    return pdf


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--show", action="store_true")
    a = ap.parse_args()
    from playwright.sync_api import sync_playwright

    polite = Polite(daily_limit=DAY_MAX, site="kapa")
    with connect() as conn, run(conn, "kapa_pdf", "감정평가서 원본") as job:
        todo = targets(conn, date.today(), 1 if a.probe else DAY_MAX)
        print(f"대상 {len(todo)}건")
        if not todo:
            if a.probe:  # 감정서 번호를 아직 안 받았거나 입찰일이 지난 사건뿐
                print(
                    "   감정서 번호가 있는 진행 사건이 없어요 — 새 코드로 court_docs --case 를 먼저 돌려 주세요"
                )
            return
        with sync_playwright() as p:
            browser = launch_chrome(p, headless=not a.show)
            ctx = browser.new_context(accept_downloads=True)
            page = ctx.new_page()
            try:
                for case_id, info in todo:
                    url = view_url(info)
                    if not url:
                        continue
                    probe: list[str] | None = [url] if a.probe else None
                    try:
                        res = polite.call(
                            lambda u=url, pr=probe: {
                                "ok": True,
                                "pdf": fetch_pdf(ctx, page, u, pr),
                            },
                            case_id,
                        )
                    except DailyLimitReached:
                        print("하루 한도 — 나머지는 내일")
                        break
                    pdf = res.get("pdf")
                    if probe is not None:
                        PROBE_LOG.parent.mkdir(exist_ok=True)
                        PROBE_LOG.write_text("\n\n".join(probe), encoding="utf-8")
                        print(f"적어 둠: {PROBE_LOG}")
                    if not pdf:
                        print(f"   {case_id} 원본 못 받음")
                        continue
                    data = {"no": info["aeeWevlNo"], **read_pdf(pdf)}
                    conn.execute(
                        "insert into raw.court_doc_raw (case_id, doc_kind, payload, checksum) values (%s,'appraisal_pdf',%s,%s) on conflict do nothing",
                        (case_id, Jsonb(data), checksum(data)),
                    )
                    conn.commit()
                    job.count += 1
                    print(f"   {case_id} {data['firm'] or '회사 이름 못 찾음'} · {data['pages']}쪽")
                    polite.between_cases()
            finally:
                browser.close()
    print(f"끝: {job.count}건")


if __name__ == "__main__":
    main()
