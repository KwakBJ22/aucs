"""사건 서류 데이터 수집: 사건내역·기일·문건송달·현황조사·물건상세 (화면과 같은 요청, 로그인 없음).

    uv run python -m aucs_workers.collectors.court_docs --archive        # 보관 수집 (서울·경기 아파트·다세대·오피스텔, 관심 물건 먼저)
    uv run python -m aucs_workers.collectors.court_docs --watched        # 관심에 담은 뒤 아직 서류를 안 받은 물건만(낮에 매시)
    uv run python -m aucs_workers.collectors.court_docs --case B000250 2025타경55580

보관 규칙(10/16 결정): 매각기일 14일 안 1번 → 7일 안 1번 더 → 기일 뒤 1번, 하루 최대 150건(기일 가까운 순).
감정평가서·명세서 PDF 는 받지 않습니다(데이터만). 원본은 raw 에 추가만 하므로
다시 받을 때 비어 온 종류는 예전 것이 그대로 남습니다.
"""

import argparse
import re
from datetime import date, timedelta
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from aucs_workers.collectors.browser import launch_chrome
from aucs_workers.collectors.court_site import COURTS
from aucs_workers.collectors.parse import checksum
from aucs_workers.collectors.polite import Polite
from aucs_workers.db import connect
from aucs_workers.extract.case_docs import apply_case_docs
from aucs_workers.jobs.runlog import run
from aucs_workers.photos import pull_pics
from aucs_workers.photos import store as store_photos

CASE_PAGE = "https://www.courtauction.go.kr/pgj/index.on?w2xPath=/pgj/ui/pgj100/PGJ159M00.xml"
ARCHIVE_MAX = 150
# 보관 대상 용도 (10/18: 아파트 → 다세대·연립·오피스텔까지, 하루 한도는 그대로)
ARCHIVE_USAGES = ("아파트", "다세대", "연립주택,다세대,빌라", "오피스텔")

JS_POST = r"""
async ([path, body]) => {
  const r = await fetch(path, { method: 'POST', credentials: 'include',
    headers: { 'Content-Type': 'application/json;charset=UTF-8', 'Accept': 'application/json' },
    body: JSON.stringify(body) });
  const t = await r.text();
  try { const j = JSON.parse(t); return { ok: r.ok && j.status == 200, status: r.status, msg: j.message, data: j.data }; }
  catch (e) { return { ok: false, status: r.status, msg: t.slice(0, 200) }; }
}
"""


def internal_no(case_no: str) -> str:
    """2023타경113350 → 20230130113350 (법원 내부 사건번호)."""
    m = re.fullmatch(r"(\d{4})타경(\d+)", case_no.replace(" ", ""))
    if not m:
        raise ValueError(f"사건번호 형식이 아닙니다: {case_no}")
    return f"{m.group(1)}0130{int(m.group(2)):06d}"


def archive_due(sale_date: date, last_fetched: date | None, today: date) -> tuple[bool, int]:
    """(받을 차례인지, 순서). 기일 14일 안 처음 → 7일 안 한 번 더 → 기일 뒤 한 번. 지난 것은 맨 뒤."""
    left = (sale_date - today).days
    if left > 14 or left < -7:
        return False, 0
    if left >= 0:
        need = last_fetched is None or (left <= 7 and last_fetched < sale_date - timedelta(days=7))
        return need, left
    return last_fetched is None or last_fetched <= sale_date, 100 - left


WATCHED_SQL = """
select c.court_code, c.case_no
from app.watch_items w
join core.items i using (item_id) join core.cases c using (case_id)
where i.sale_date between %(from)s and %(to)s and i.status_code is distinct from 'gone'
group by c.case_id, c.court_code, c.case_no
having coalesce((select max(fetched_at) from raw.court_doc_raw r where r.case_id = c.case_id), '-infinity')
       < max(w.created_at)
order by min(i.sale_date)
"""


def watched_targets(conn: psycopg.Connection, today: date) -> list[tuple[str, str]]:
    """관심에 담은 뒤 아직 서류를 안 받은 사건(용도 상관없이, 기일 60일 안). 「관심 담으면 바로 준비」(16)."""
    rows = conn.execute(
        WATCHED_SQL, {"from": today - timedelta(days=7), "to": today + timedelta(days=60)}
    ).fetchall()
    return [(court, case_no) for court, case_no in rows if court in COURTS]


PHOTO_SQL = """
select c.court_code, c.case_no, min(i.sale_date) as d,
       bool_or(exists (select 1 from app.watch_items w where w.item_id = i.item_id)) as watched
from core.cases c join core.items i using (case_id)
where i.sale_date >= %s
  and exists (select 1 from raw.court_doc_raw r where r.case_id = c.case_id and r.doc_kind like 'item_detail_%%')
  and not exists (select 1 from core.item_photos p where p.case_id = c.case_id)
group by 1, 2 order by watched desc, d
limit %s
"""


def photo_targets(conn: psycopg.Connection, today: date) -> list[tuple[str, str]]:
    """사진 다시 받기(11/1 사진을 원문에서 빼면서 키가 비어 못 옮긴 것): 관심 먼저, 기일 가까운 순."""
    rows = conn.execute(PHOTO_SQL, (today, ARCHIVE_MAX * 4)).fetchall()
    return [(court, case_no) for court, case_no, _, _ in rows if court in COURTS]


def archive_targets(conn: psycopg.Connection, today: date) -> list[tuple[str, str]]:
    rows = conn.execute(
        """select c.court_code, c.case_no, min(i.sale_date),
                  (select max(fetched_at)::date from raw.court_doc_raw r where r.case_id = c.case_id)
           from core.items i join core.cases c using (case_id)
           where i.usage_name = any(%s) and i.sido in ('서울특별시', '경기도')
             and i.sale_date between %s and %s
           group by c.case_id, c.court_code, c.case_no""",
        (list(ARCHIVE_USAGES), today - timedelta(days=7), today + timedelta(days=14)),
    ).fetchall()
    todo = []
    for court, case_no, sale_date, last in rows:
        need, rank = archive_due(sale_date, last, today)
        if need and court in COURTS:
            todo.append((rank, court, case_no))
    todo.sort()
    first = watched_targets(conn, today)  # 관심 물건 먼저
    rest = [(c, n) for _, c, n in todo if (c, n) not in set(first)]
    return (first + rest)[:ARCHIVE_MAX]


def fetch_case(page: Any, polite: Polite, court: str, case_no: str) -> dict[str, dict[str, Any]]:
    """한 사건의 서류 데이터를 종류별로 받습니다. 물건상세가 실패하면 그 종류만 빠집니다."""
    cs = internal_no(case_no)

    def post(path: str, body: dict[str, Any], label: str) -> dict[str, Any]:
        res = polite.call(lambda: dict(page.evaluate(JS_POST, [path, body])), f"{case_no} {label}")
        return dict(res.get("data") or {})

    out: dict[str, dict[str, Any]] = {}
    out["case_info"] = post(
        "/pgj/pgj15A/selectAuctnCsSrchRslt.on",
        {"dma_srchCsDtlInf": {"cortOfcCd": court, "csNo": case_no}},
        "사건내역",
    )
    out["schedule"] = post(
        "/pgj/pgj15A/selectCsDtlDxdyDts.on",
        {"dma_srchDxdyDtsLst": {"cortOfcCd": court, "csNo": cs}},
        "기일내역",
    )
    out["deliveries"] = post(
        "/pgj/pgj15A/selectDlvrOfdocDtsDtl.on",
        {"dma_srchDlvrOfdocDts": {"cortOfcCd": court, "csNo": cs, "srchFlag": "F"}},
        "문건송달",
    )
    out["status_report"] = post(
        "/pgj/pgj15B/selectCurstExmndc.on",
        {
            "dma_srchCurstExmn": {
                "cortOfcCd": court,
                "csNo": case_no,
                "auctnInfOriginDvsCd": "2",
                "ordTsCnt": "",
            }
        },
        "현황조사",
    )
    seqs = sorted(
        {
            int(g.get("dspslGdsSeq") or 1)
            for g in out["case_info"].get("dlt_dspslGdsDspslObjctLst") or []
        }
        or {1}
    )
    for seq in seqs:
        body = {
            "dma_srchGdsDtlSrch": {
                "csNo": cs,
                "cortOfcCd": court,
                "dspslGdsSeq": seq,
                "pgmId": "PGJ15BM01",
                "srchInfo": {},
            }
        }
        try:
            out[f"item_detail_{seq}"] = post(
                "/pgj/pgj15B/selectAuctnCsSrchRslt.on", body, f"물건상세{seq}"
            )
        except Exception as e:  # noqa: BLE001 — 물건상세만 실패하면 나머지는 저장
            if type(e).__name__ == "Blocked" and "물건상세" not in str(e):
                raise
    return out


def save_case(
    conn: psycopg.Connection, court: str, case_no: str, docs: dict[str, dict[str, Any]]
) -> None:
    case_id = f"{court}-{case_no}"
    conn.execute(
        "insert into core.cases (case_id, court_code, case_no) values (%s,%s,%s) on conflict do nothing",
        (case_id, court, case_no),
    )
    pics: list[tuple[str, str]] = []
    for kind in list(docs):
        if kind.startswith("item_detail_") and docs[kind]:
            docs[kind], got = pull_pics(
                docs[kind]
            )  # 사진 글자는 원문에서 빼고 줄여서 Storage 로(11/1)
            pics += got
    for kind, data in docs.items():
        if not data:
            continue  # 비어 온 종류는 넣지 않음 → 예전 것 유지
        conn.execute(
            "insert into raw.court_doc_raw (case_id, doc_kind, payload, checksum) values (%s,%s,%s,%s) on conflict do nothing",
            (case_id, kind, Jsonb(data), checksum(data)),
        )
    apply_case_docs(conn, case_id, docs)
    store_photos(conn, case_id, pics)


def main() -> None:
    from playwright.sync_api import sync_playwright

    ap = argparse.ArgumentParser()
    ap.add_argument("--archive", action="store_true")
    ap.add_argument("--watched", action="store_true", help="관심에 담은 뒤 아직 안 받은 서류만")
    ap.add_argument(
        "--photos", action="store_true", help="진행 중인데 현장 사진이 없는 사건만 다시 받기(11/1)"
    )
    ap.add_argument("--case", nargs=2, metavar=("법원코드", "사건번호"))
    ap.add_argument("--show", action="store_true")
    a = ap.parse_args()
    polite = Polite(daily_limit=ARCHIVE_MAX * 12)
    with connect() as conn, run(conn, "court_docs", "사건 서류 보관") as job:
        if a.case:
            targets = [tuple(a.case)]
        elif a.watched:
            targets = watched_targets(conn, date.today())
        elif a.photos:
            targets = photo_targets(conn, date.today())
        else:
            targets = archive_targets(conn, date.today())
        print(f"대상 {len(targets)}건")
        if not targets:
            return
        with sync_playwright() as p:
            browser = launch_chrome(p, headless=not a.show)
            page = browser.new_page()
            page.goto(CASE_PAGE, wait_until="networkidle", timeout=60000)
            try:
                for court, case_no in targets:
                    save_case(conn, court, case_no, fetch_case(page, polite, court, case_no))
                    conn.commit()
                    job.count += 1
                    polite.between_cases()
            finally:
                browser.close()
    print(f"끝: {job.count}건")


if __name__ == "__main__":
    main()
