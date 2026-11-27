"""매각물건명세서 원본 받기 → 임차인 줄(core.tenants source='spec') — 11/26 지시 1126a.

법원은 명세서를 매각기일 1주 전쯤 공개(물건상세 「매각물건명세서」 단추가 그때 열림) → 입찰 7일 안 물건마다 한 번.
받는 길(11/26 법원 화면에서 확인):
  ① courtauction POST /pgj/pgj15B/insertDspslGdsSpecArtcWdrwInf.on (물건상세의 dspslGdsSpcfcEcdocId) — 화면과 같은 머리
     (submissionid · SC-Pgmid · SC-Userid)가 있어야 함(없으면 500). 법원 하루 한도에 1번으로 셈.
  ② ecfs.scourt.go.kr 문서뷰어(주소?paramData=base64{encParam}) → pvo.scourt.go.kr/streamdocs 가 쪽마다 글(texts/N)을 줌
     — 다른 서버라 법원경매정보 한도와 따로. 글로 표를 다시 짬(extract/spec.py).
원본(낱말과 자리)은 raw.court_doc_raw doc_kind='spec_<물건번호>' 에 · 임차인 줄은 core.tenants(source='spec')에 —
명세서를 받은 물건은 현황조사서 임차인 줄을 지움(같은 사람을 두 번 세지 않게. 명세서가 법원이 정리한 최종 표).

    uv run python -m aucs_workers.collectors.court_spec            # 오늘 ~ 입찰 7일 안(급한 것), 입찰일 이른 순
    uv run python -m aucs_workers.collectors.court_spec --old      # 입찰 지난 60일, 없어지기 직전(오래된) 것부터
    uv run python -m aucs_workers.collectors.court_spec --case B000210 2026타경121 1
"""

import argparse
import base64
import json
import re
from datetime import date, timedelta
from typing import Any

import psycopg
from aucs_rules.courts import COURTS
from psycopg.types.json import Jsonb

from aucs_workers.collectors.browser import launch_chrome, lean_context
from aucs_workers.collectors.court_docs import (
    ARCHIVE_USAGES,
    AREA,
    CASE_PAGE,
    LIVE_FIRST,
    REAL_ESTATE,
)
from aucs_workers.collectors.parse import checksum
from aucs_workers.collectors.polite import DailyLimitReached, Polite
from aucs_workers.db import connect
from aucs_workers.doc_files import save_file
from aucs_workers.extract.spec import parse_tenants, words_from_texts
from aucs_workers.jobs.runlog import run

SPEC_DAYS = 7  # 입찰 이만큼 안(법원 1주 전 공개)
# 11/27: 입찰이 지난 물건도 명세서가 열려 있음(10/19 입찰 물건 확인) — 없어지기 전에 가장 오래된 것부터 받음
SPEC_BACK_DAYS = 60
SPEC_MAX = 300  # 한 번에 꺼낼 물건 수 — 실제 양은 시간 몫이 정함
VIEW_WAIT_MS = 25000  # 뷰어가 쪽 글을 다 줄 때까지 최대

JS_SPEC = r"""
async (body) => {
  const r = await fetch('/pgj/pgj15B/insertDspslGdsSpecArtcWdrwInf.on', { method: 'POST', credentials: 'include',
    headers: { 'Content-Type': 'application/json;charset=UTF-8', 'Accept': 'application/json',
               'submissionid': 'mf_wfm_mainFrame_sbm_dspslSpcfcViewOpen', 'SC-Pgmid': 'PGJ15AF01', 'SC-Userid': 'NONUSER' },
    body: JSON.stringify(body) });
  const t = await r.text();
  try { const j = JSON.parse(t); return { status: r.status, data: j.data, msg: j.message || (j.errors || {}).errorMessage }; }
  catch (e) { return { status: r.status, msg: t.slice(0, 200) }; }
}"""

TARGETS_SQL = f"""
select i.item_id, i.case_id, c.court_code, c.case_no, i.item_no,
       d.payload->'dma_result'->'dspslGdsDxdyInfo'->>'csNo' as cs_no,
       d.payload->'dma_result'->'dspslGdsDxdyInfo'->>'dspslGdsSpcfcEcdocId' as ecdoc
from core.items i join core.cases c using (case_id)
join lateral (select payload from raw.court_doc_raw r where r.case_id = i.case_id and r.doc_kind = 'item_detail_' || i.item_no
              and jsonb_typeof(r.payload->'dma_result') = 'object' order by r.fetched_at desc limit 1) d on true
where {AREA} and {REAL_ESTATE} and i.status_code is distinct from 'gone' and i.item_no is not null
  and i.sale_date between %(from)s and %(to)s
  and coalesce(d.payload->'dma_result'->'dspslGdsDxdyInfo'->>'dspslGdsSpcfcEcdocId', '') <> ''
  -- 같은 문서를 이미 글까지 받았으면 건너뜀 · 못 받았으면(아직 비공개 등) 하루 뒤 다시
  and not exists (select 1 from raw.court_doc_raw s where s.case_id = i.case_id and s.doc_kind = 'spec_' || i.item_no
                  and s.payload->>'ecdoc' = d.payload->'dma_result'->'dspslGdsDxdyInfo'->>'dspslGdsSpcfcEcdocId'
                  and (((s.payload->>'pages')::int > 0 and s.payload ? 'pdf') or s.fetched_at > now() - interval '1 day'))
  -- 11/27: 원본 파일을 보관하기 전에 글만 읽은 것(pdf 표시 없음)은 한 번 더 받아 원본을 남김
order by i.sale_date, {LIVE_FIRST}
limit %(n)s"""


def targets(conn: psycopg.Connection, today: date, mode: str = "soon") -> list[dict[str, Any]]:
    """soon = 오늘 ~ 입찰 7일 안(급한 것) · old = 지난 60일(없어지기 직전 것부터). 둘 다 입찰일 이른 순."""
    if mode == "old":
        frm, to = today - timedelta(days=SPEC_BACK_DAYS), today - timedelta(days=1)
    else:
        frm, to = today, today + timedelta(days=SPEC_DAYS)
    rows = conn.execute(
        TARGETS_SQL,
        {"from": frm, "to": to,
         "usages": list(ARCHIVE_USAGES), "n": SPEC_MAX},
    ).fetchall()  # fmt: skip
    cols = ["item_id", "case_id", "court", "case_no", "item_no", "cs_no", "ecdoc"]
    return [dict(zip(cols, r, strict=True)) for r in rows if r[2] in COURTS]


def open_spec(page: Any, polite: Polite, t: dict[str, Any]) -> dict[str, Any]:
    """① 법원경매정보에 1번 — 뷰어 주소 · encParam. 500(아직 비공개 · 문서 없음)은 막힘이 아니므로 그대로 돌려줌."""
    body = {"dma_dspslGdsSpecLog": {"cortOfcCd": t["court"], "csNo": t["cs_no"], "dspslGdsSeq": t["item_no"],
            "orvParam": "", "dspslGdsSpcfcEcdocId": t["ecdoc"], "cortAuctnMbrsId": "NONUSER", "docFlag": "1",
            "dspslDxdyPbancEcdocId": ""}}  # fmt: skip

    def one() -> dict[str, Any]:
        res = dict(page.evaluate(JS_SPEC, body))
        # 「비정상 IP」만 막힘 처리(polite 가 멈춤) — 그 밖의 오류는 이 물건만 건너뜀(11/26 06시 500 을 막힘으로 적은 일)
        res["ok"] = "비정상" not in str(res.get("msg") or "")
        return res

    return polite.call(one, f"{t['case_no']} 명세서{t['item_no']}")


def read_viewer(
    ctx: Any, url: str, enc: str, pdf: list[bytes] | None = None
) -> dict[int, list[dict[str, Any]]]:
    """② 뷰어를 열어 쪽마다 글(texts/N)을 모음. 화면에 안 보인 쪽은 틀을 내려 부르게 함.
    11/27: 뷰어가 받아 오는 원본 PDF 를 pdf 에 담음(쪽 그림 · 글꼴은 lean_context 가 막음)."""
    pd = base64.b64encode(
        json.dumps({"encParam": enc, "pspSid": "NA", "pspTkn": "NA"}).encode()
    ).decode()
    pages: dict[int, list[dict[str, Any]]] = {}
    meta: dict[str, int] = {}

    def on_resp(r: Any) -> None:
        u = r.url.split("?")[0]
        if pdf is not None and not pdf:
            try:
                ct = (r.headers.get("content-type") or "").lower()
                if "pdf" in ct or "getpdf" in u.lower():
                    b = r.body()
                    if b[:4] == b"%PDF":
                        pdf.append(b)
            except Exception:  # noqa: BLE001 — 원본을 못 받아도 글은 씀
                pass
        if "/streamdocs/v4/documents/" not in u:
            return
        try:
            if "/texts/" in u:
                pages[int(u.rsplit("/", 1)[1])] = json.loads(r.body())
            elif u.endswith("/document"):
                raw = r.body().decode("utf-8", "replace")
                meta["n"] = len(
                    json.JSONDecoder().raw_decode(raw[raw.find("{") :])[0].get("layout") or []
                )
        except Exception:  # noqa: BLE001 — 한 쪽을 못 읽어도 나머지는 씀
            pass

    v = ctx.new_page()
    try:
        v.on("response", on_resp)
        v.goto(f"{url}?paramData={pd}", timeout=60000)
        waited = 0
        while waited < VIEW_WAIT_MS and not (meta.get("n") and len(pages) >= meta["n"]):
            v.wait_for_timeout(500)
            waited += 500
            if waited % 3000 == 0 and meta.get("n") and len(pages) < meta["n"]:
                for fr in v.frames:
                    if "pvo." in fr.url:
                        fr.evaluate(
                            "document.querySelectorAll('*').forEach(e=>{if(e.scrollHeight>e.clientHeight+50){e.scrollTop+=1500}})"
                        )
    finally:
        v.close()
    return pages


def save(
    conn: psycopg.Connection, t: dict[str, Any], pages: dict[int, list[dict[str, Any]]], status: int,
    pdf: bytes | None = None,
) -> int:  # fmt: skip
    words = words_from_texts(pages)
    kept = False
    if pdf:
        try:
            sd = conn.execute("select sale_date from core.items where item_id = %s", (t["item_id"],)).fetchone()
            r = save_file(conn, t["case_id"], t["item_no"], "spec", "court", pdf,
                          sale_date=sd[0] if sd else None, pages=len(pages) or None)  # fmt: skip
            kept = bool(r.get("path"))
            if r.get("error"):
                print(f"   {t['case_no']}-{t['item_no']} 원본 보관 실패 {r['error']}", flush=True)
        except Exception as e:  # noqa: BLE001
            print(f"   {t['case_no']}-{t['item_no']} 원본 보관 실패 {type(e).__name__}", flush=True)
    payload = {
        "ecdoc": t["ecdoc"],
        "pages": len(pages),
        "status": status,
        "pdf": kept,  # 11/27 원본 파일을 core.doc_files 에 남겼는지
        "words": [list(w) for w in words],
    }
    conn.execute(
        "insert into raw.court_doc_raw (case_id, doc_kind, payload, checksum) values (%s,%s,%s,%s) on conflict do nothing",
        (t["case_id"], f"spec_{t['item_no']}", Jsonb(payload), checksum(payload)),
    )
    if not pages:
        return 0
    return save_tenants(conn, t, words)


def reparse(conn: psycopg.Connection) -> tuple[int, int]:
    """받아 둔 명세서 원본 낱말을 법원에 다시 묻지 않고 다시 읽음(11/27 — 읽는 규칙을 고쳤을 때)."""
    rows = conn.execute(
        """select distinct on (d.case_id, d.doc_kind) d.case_id, i.item_id, d.payload->'words' as words
           from raw.court_doc_raw d join core.items i on i.case_id = d.case_id and d.doc_kind = 'spec_' || i.item_no
           where d.doc_kind like 'spec\\_%%' and jsonb_array_length(coalesce(d.payload->'words', '[]')) > 0
           order by d.case_id, d.doc_kind, d.fetched_at desc"""
    ).fetchall()
    n = 0
    for case_id, item_id, ws in rows:
        words = [tuple(w) for w in ws]
        n += save_tenants(conn, {"case_id": case_id, "item_id": item_id}, words)
        conn.commit()
    return len(rows), n


def save_tenants(conn: psycopg.Connection, t: dict[str, Any], words: list[Any]) -> int:
    res = parse_tenants(words)
    conn.execute("delete from core.tenants where item_id = %s and source = 'spec'", (t["item_id"],))
    for r in res["rows"]:
        name = r.get("name") or ""
        conn.execute(
            """insert into core.tenants (case_id, item_id, name_masked, name_raw, occupied_part, move_in_date, fixed_date,
                   claim_date, deposit_krw, monthly_rent_krw, has_lease_registration, source, fetched_at)
               values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'spec', now())""",
            (t["case_id"], t["item_id"], (name[0] + "○○") if name else None, name or None, r.get("part"),
             r.get("move_in_date"), r.get("fixed_date"), r.get("claim_date"), r.get("deposit_krw"),
             r.get("monthly_rent_krw"), bool(re.search(r"임차권", (r.get("title") or "") + (r.get("source") or "")))),
        )  # fmt: skip
    drop_status_rows(conn, t["case_id"], t["item_id"])
    # 다시 분석(--stale 이 바뀐 물건만 봄)
    conn.execute("update core.items set updated_at = now() where item_id = %s", (t["item_id"],))
    return len(res["rows"])


def drop_status_rows(conn: psycopg.Connection, case_id: str, item_id: str) -> None:
    """명세서를 받은 물건은 현황조사서 임차인 줄을 지움 — 그 호 줄, 물건이 하나뿐인 사건이면 사건 전체 줄도."""
    conn.execute(
        """delete from core.tenants t where t.case_id = %s and t.source = 'status_report'
           and (t.item_id = %s or (t.item_id is null and (select count(*) from core.items i
                where i.case_id = t.case_id and i.status_code is distinct from 'gone') = 1))""",
        (case_id, item_id),
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", nargs=3, metavar=("법원코드", "사건번호", "물건번호"))
    ap.add_argument("--show", action="store_true")
    ap.add_argument("--old", action="store_true", help="입찰 지난 60일(없어지기 직전 것부터)")
    ap.add_argument("--reparse", action="store_true", help="받아 둔 원본을 다시 읽기만(법원에 안 물음)")
    a = ap.parse_args()
    if a.reparse:
        with connect() as conn, run(conn, "court_spec_reparse", "매각물건명세서 원본 다시 읽기") as job:
            docs, n = reparse(conn)
            job.count = docs
        print(f"끝: 명세서 {docs}건 다시 읽음 · 임차인 줄 {n}", flush=True)
        return
    from playwright.sync_api import sync_playwright

    polite = Polite(daily_limit=SPEC_MAX * 2, hourly=not a.case)
    with connect() as conn, run(conn, "court_spec", "매각물건명세서 원본") as job:
        today = date.today()
        if a.case:
            ts = [t for t in targets_all(conn, a.case)]
        else:
            ts = targets(conn, today, "old" if a.old else "soon")
        print(f"대상 {len(ts)}건", flush=True)
        if not ts:
            return
        got = rows = 0
        with sync_playwright() as p:
            browser = launch_chrome(p, headless=not a.show)
            ctx = lean_context(browser)  # 11/27 사진 · 글꼴 · 쪽 그림은 안 받고, 뷰어 화면 파일은 한 번만
            page = ctx.new_page()
            page.goto(CASE_PAGE, wait_until="networkidle", timeout=60000)
            try:
                for t in ts:
                    try:
                        res = open_spec(page, polite, t)
                    except DailyLimitReached:
                        print("요청 한도(이번 시간 몫 또는 하루) — 다음 시간에 이어서", flush=True)
                        break
                    info = (res.get("data") or {}).get("dma_dspslSpcfcInfo") or {}
                    pages: dict[int, list[dict[str, Any]]] = {}
                    pdf: list[bytes] = []
                    if info.get("encParam") and info.get("url"):
                        try:
                            pages = read_viewer(ctx, info["url"], info["encParam"], pdf)
                        except Exception as e:  # noqa: BLE001
                            print(
                                f"   {t['case_no']}-{t['item_no']} 뷰어 실패 {type(e).__name__}",
                                flush=True,
                            )
                    rows += save(conn, t, pages, int(res.get("status") or 0), pdf[0] if pdf else None)
                    conn.commit()
                    got += 1 if pages else 0
                    job.count = got
                    polite.between_cases()
            finally:
                browser.close()
    print(f"끝: 명세서 {got}건 · 임차인 줄 {rows}", flush=True)


def targets_all(conn: psycopg.Connection, case: list[str]) -> list[dict[str, Any]]:
    """--case: 기간 · 이미 받음과 상관없이 그 물건 하나."""
    court, case_no, seq = case
    row = conn.execute(
        """select i.item_id, i.case_id, d.payload->'dma_result'->'dspslGdsDxdyInfo'->>'csNo',
                  d.payload->'dma_result'->'dspslGdsDxdyInfo'->>'dspslGdsSpcfcEcdocId'
           from core.items i join lateral (select payload from raw.court_doc_raw r where r.case_id = i.case_id
             and r.doc_kind = 'item_detail_' || i.item_no and jsonb_typeof(r.payload->'dma_result') = 'object'
             order by r.fetched_at desc limit 1) d on true
           where i.case_id = %s and i.item_no = %s""",
        (f"{court}-{case_no}", int(seq)),
    ).fetchone()
    if not row:
        return []
    return [{"item_id": row[0], "case_id": row[1], "court": court, "case_no": case_no, "item_no": int(seq),
             "cs_no": row[2], "ecdoc": row[3]}]  # fmt: skip


if __name__ == "__main__":
    main()
