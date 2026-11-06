"""감정평가서 원본 받기 (11/4 대표님 — 한국감정평가사협회 사용 허락, 법원 「감정평가서 보기」와 같은 길).

11/4 대표님 브라우저에서 본 길: 법원 물건 화면의 「감정평가서 보기」 → 법원 팝업(PGJ15BP03) → KAPA 열람 페이지 →
그 안의 틀이 `https://ca.kapanet.or.kr/{8자}/{명령횟차 3자리}/{8자}/{감정서 번호}.pdf` 를 엶.
앞뒤 8자는 계산할 수 없고 팝업 안에서만 채워지므로, **법원 화면을 실제로 열고 그 화면의 팝업을 띄워**(단추가 부르는 것과 같은 함수)
브라우저가 여는 PDF 주소를 받습니다. 주소·머리말을 꾸미지 않습니다.
받은 PDF 는 저장하지 않고 회사 이름 · 쪽수 · 앞부분 글만 raw 'appraisal_pdf' 에 남깁니다.
팝업 한 번 = 법원 요청 한 번(감정평가서 정보)으로 셈 — 법원 하루 한도·시간 몫(polite.py) 안에서만.

    uv run python -m aucs_workers.collectors.kapa_pdf            # 관심 → 입찰 가까운 순, 하루 150건
    uv run python -m aucs_workers.collectors.kapa_pdf --probe    # 한 건만 — 무슨 일이 있었는지 logs/kapa_probe.txt
    uv run python -m aucs_workers.collectors.kapa_pdf --probe --headless   # 예전처럼 창 없는 크롬으로(견줘 보기)

11/7: 창 없는 크롬(headless)에서는 KAPA 화면이 비어 나옴(휴대폰·보통 크롬은 열림) → 기본을 「창을 화면 밖에 띄운 보통 크롬」으로.
    uv run python -m aucs_workers.collectors.kapa_pdf --probe --show --case B000210 2023타경106499   # 그 사건, 창을 띄워서
"""

import argparse
import time
from datetime import date
from pathlib import Path
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from aucs_workers.collectors.browser import launch_chrome
from aucs_workers.collectors.court_docs import JS_POST
from aucs_workers.collectors.parse import checksum
from aucs_workers.collectors.polite import DailyLimitReached, Polite
from aucs_workers.db import connect
from aucs_workers.extract.appraisal_pdf import read_pdf
from aucs_workers.jobs.runlog import run

DAY_MAX = 150
COURT_PAGE = "https://www.courtauction.go.kr/pgj/index.on?w2xPath=/pgj/ui/pgj100/PGJ151F00.xml"
WAIT_SEC = 20
MISS_STOP = (
    3  # 연달아 이만큼 못 받으면 하루 쉼(KAPA 가 원본을 안 줄 때 법원·KAPA 를 헛되이 두드리지 않게)
)
PAUSE = Path(__file__).resolve().parents[4] / "logs" / "kapa_paused.txt"
PROBE_LOG = Path(__file__).resolve().parents[4] / "logs" / "kapa_probe.txt"

# 법원 화면의 「감정평가서 보기」 단추가 부르는 것과 같은 팝업(PGJ15BM01.xml scwin.aeeWevlPopUp)
JS_OPEN = r"""
([id, court, cs, dxdy]) => {
  let name = '';
  try { name = pgjUtil.getCortOfcNm('B', court) || ''; } catch (e) {}
  com.win.openPopup('/pgj/ui/pgj100/PGJ15BP03.xml',
    { id, type: 'wframePopup', popupName: '감정평가서', top: 20, left: 20, width: 900, height: 850, modal: true },
    { paramObj: { cortOfcCd: court, cortSptNm: name, csNo: cs, dxdy } });
  return name;
}
"""
JS_CLOSE = r"""
(id) => { try { com.win.closePopup(id); } catch (e) {} const el = document.getElementById(id); if (el) el.remove(); }
"""


def targets(conn: psycopg.Connection, today: date, limit: int) -> list[tuple[str, dict[str, Any]]]:
    """감정서 번호가 있고 원본을 아직 안 받은 진행 사건 — 관심 물건 먼저, 그다음 입찰 가까운 순."""
    rows = conn.execute(
        """select a.case_id, a.payload -> 'info' as info
           from (select distinct on (case_id) case_id, payload from raw.court_doc_raw
                 where doc_kind = 'appraisal' order by case_id, fetched_at desc) a
           join lateral (select min(i.sale_date) as d,
                                bool_or(exists (select 1 from app.watch_items w where w.item_id = i.item_id)) as watched
                         from core.items i where i.case_id = a.case_id and i.sale_date >= %s) s on s.d is not null
           where a.payload -> 'info' ->> 'aeeWevlNo' is not null
             and not exists (select 1 from raw.court_doc_raw p where p.case_id = a.case_id and p.doc_kind = 'appraisal_pdf'
                             and p.payload ->> 'no' = a.payload -> 'info' ->> 'aeeWevlNo')
           order by s.watched desc, s.d limit %s""",
        (today, limit),
    ).fetchall()
    return [(r[0], dict(r[1])) for r in rows]


def open_and_catch(page: Any, info: dict[str, Any], n: int, probe: list[str] | None) -> str | None:
    """법원 화면에서 감정평가서 팝업을 띄우고, 브라우저가 여는 KAPA PDF 주소를 잡아 돌려줌(못 잡으면 None)."""
    seen: list[str] = []
    kapa: list[str] = []  # 시험 기록용 — KAPA 쪽으로 간 요청 전부

    def on_request(req: Any) -> None:
        u = req.url
        if "kapanet" in u:
            kapa.append(f"{req.resource_type} {u[:160]}")
            if u.lower().split("?")[0].endswith(".pdf"):
                seen.append(u)

    pid = f"aucsAeeWevl{n}"
    page.context.on("request", on_request)
    try:
        # 사람이 하듯 물건상세를 먼저 연 뒤 단추를 누름(11/4 — 대표님 화면은 물건상세에서 눌렀을 때 원본이 떴음)
        seq = int(info.get("dspslGdsSeq") or 1)
        det = page.evaluate(JS_POST, ["/pgj/pgj15B/selectAuctnCsSrchRslt.on", {"dma_srchGdsDtlSrch": {
            "csNo": info["csNo"], "cortOfcCd": info["cortOfcCd"], "dspslGdsSeq": seq,
            "pgmId": "PGJ15BM01", "srchInfo": {}}}])  # fmt: skip
        if probe is not None:
            probe.append(f"물건상세 {det.get('status')} ok={det.get('ok')}")
        name = page.evaluate(JS_OPEN, [pid, info["cortOfcCd"], info["csNo"], ""])
        if probe is not None:
            probe.append(f"팝업 열음 {info['cortOfcCd']} {info['csNo']} ({name})")
        for _ in range(WAIT_SEC * 2):
            if seen:
                break
            page.wait_for_timeout(500)
    finally:
        page.context.remove_listener("request", on_request)
        try:
            page.evaluate(JS_CLOSE, pid)
            page.evaluate(JS_CLOSE, "aeeWevlPopUp")
        except Exception:  # noqa: BLE001
            pass
    if probe is not None:
        probe.append(f"잡은 PDF 주소: {seen[:3]}")
        probe.append("KAPA 쪽 요청:\n  " + "\n  ".join(kapa[:20]))
    return seen[0] if seen else None


def download(page: Any, url: str, probe: list[str] | None) -> bytes | None:
    """잡은 PDF 주소를 같은 브라우저 세션으로 받음(브라우저가 방금 연 것과 같은 주소)."""
    r = page.context.request.get(url, timeout=180000)
    b = r.body()
    if probe is not None:
        probe.append(f"받기 {r.status} {r.headers.get('content-type')} {len(b)}B")
    return bytes(b) if b[:4] == b"%PDF" else None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--show", action="store_true", help="창을 화면 안에 띄움")
    ap.add_argument("--headless", action="store_true", help="예전처럼 창 없는 크롬(견줘 보기용)")
    ap.add_argument("--case", nargs=2, metavar=("법원코드", "사건번호"), help="이 사건만(시험용)")
    a = ap.parse_args()
    from playwright.sync_api import sync_playwright

    if (
        PAUSE.exists()
        and time.time() - PAUSE.stat().st_mtime < 24 * 3600
        and not (a.probe or a.case)
    ):
        print(f"KAPA 원본이 안 와서 쉬는 중 — {PAUSE} 를 지우면 다시")
        return
    misses = 0
    polite = Polite(
        daily_limit=DAY_MAX, hourly=not a.probe
    )  # 팝업이 법원에 요청 한 번 — 법원 한도에 셈
    with connect() as conn, run(conn, "kapa_pdf", "감정평가서 원본") as job:
        todo = targets(conn, date.today(), 1 if a.probe else DAY_MAX)
        if a.case:
            todo = [
                t for t in targets(conn, date.today(), 100000) if t[0] == f"{a.case[0]}-{a.case[1]}"
            ]
        print(f"대상 {len(todo)}건")
        if not todo:
            if a.probe:
                print("   감정서 번호가 있는 진행 사건이 없어요 — court_docs 가 사건을 받으면 생김")
            return
        with sync_playwright() as p:
            browser = launch_chrome(p, headless=a.headless, offscreen=not a.show)
            ctx = browser.new_context(accept_downloads=True)
            page = ctx.new_page()
            probe: list[str] | None = [] if a.probe else None
            try:
                page.goto(COURT_PAGE, wait_until="networkidle", timeout=60000)
                for n, (case_id, info) in enumerate(todo):
                    try:
                        res = polite.call(
                            lambda i=info, k=n: {
                                "ok": True,
                                "url": open_and_catch(page, i, k, probe),
                            },
                            f"{case_id} 감정평가서",
                        )
                    except DailyLimitReached:
                        print("요청 한도(이번 시간 몫 또는 하루) — 다음 시간에 이어서")
                        break
                    pdf = download(page, res["url"], probe) if res.get("url") else None
                    if not pdf:
                        print(f"   {case_id} 원본 못 받음")
                        misses += 1
                        if (
                            misses >= MISS_STOP and not a.case
                        ):  # 연달아 안 오면 KAPA 쪽 문제 — 하루 쉼
                            PAUSE.write_text(
                                f"{date.today()} 연달아 {misses}건 못 받음\n", encoding="utf-8"
                            )
                            print(
                                f"   연달아 {misses}건 못 받음 — 24시간 쉼({PAUSE} 를 지우면 다시)"
                            )
                            break
                        polite.between_cases()
                        continue
                    misses = 0
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
                if probe is not None:
                    PROBE_LOG.parent.mkdir(exist_ok=True)
                    PROBE_LOG.write_text("\n".join(probe), encoding="utf-8")
                    print(f"적어 둠: {PROBE_LOG}")
                browser.close()
    print(f"끝: {job.count}건")


if __name__ == "__main__":
    main()
