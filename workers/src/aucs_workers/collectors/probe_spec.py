"""매각물건명세서 원본이 어떻게 오는지 몇 건 보기(11/26 지시 1126a) — DB 에 안 넣음, logs/probe_spec.log · probe_spec_<사건>.json.

법원 화면(11/26 확인): 물건상세 「매각물건명세서」 →
  ① courtauction POST /pgj/pgj15B/insertDspslGdsSpecArtcWdrwInf.on — 화면과 같은 머리(submissionid · SC-Pgmid · SC-Userid)가
     있어야 함(없으면 500). 답: 뷰어 주소 + encParam(한 번 쓰고 버림)
  ② ecfs.scourt.go.kr 문서뷰어(주소 + ?paramData=base64 {"encParam","pspSid":"NA","pspTkn":"NA"}) → selectDocVwrInf → getPdf
     → pvo.scourt.go.kr/streamdocs/v4/documents/<id>/texts/<쪽> 가 쪽마다 글 조각(JSON: text · 글자별 rect) — 이것을 모음
11/26 06시 첫 시험은 머리 없이 보내 500 → polite 가 막힘으로 적었음 → 이 시험은 polite.call 을 쓰지 않고 한 건에 한 번만 물음.

    uv run python -m aucs_workers.collectors.probe_spec B000211 2025타경51836 1 B000210 2026타경100740 1
"""

import base64
import json
import sys
from pathlib import Path
from typing import Any

from aucs_workers.collectors.browser import launch_chrome
from aucs_workers.collectors.court_docs import CASE_PAGE
from aucs_workers.db import connect
from aucs_workers.extract.spec import words_from_texts

LOGS = Path(__file__).resolve().parents[4] / "logs"

JS_SPEC = r"""
async (body) => {
  const r = await fetch('/pgj/pgj15B/insertDspslGdsSpecArtcWdrwInf.on', { method: 'POST', credentials: 'include',
    headers: { 'Content-Type': 'application/json;charset=UTF-8', 'Accept': 'application/json',
               'submissionid': 'mf_wfm_mainFrame_sbm_dspslSpcfcViewOpen', 'SC-Pgmid': 'PGJ15AF01', 'SC-Userid': 'NONUSER' },
    body: JSON.stringify(body) });
  const t = await r.text();
  try { const j = JSON.parse(t); return { ok: r.ok && j.status == 200, status: r.status, data: j.data, msg: j.message }; }
  catch (e) { return { ok: false, status: r.status, msg: t.slice(0, 200) }; }
}"""


def segments(pages: dict[int, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """쪽마다 글 조각 → {p, x, y, r, t}(첫 글자 왼쪽 · 위, 마지막 글자 오른쪽)."""
    out = []
    for p in sorted(pages):
        for s in pages[p]:
            rect = s.get("rect") or [{}]
            out.append({"p": p, "x": rect[0].get("left"), "y": rect[0].get("top"), "r": rect[-1].get("right"), "t": s.get("text")})
    return out


def one(browser: Any, page: Any, court: str, case_no: str, seq: int) -> list[str]:
    with connect() as conn:
        row = conn.execute(
            """select payload->'dma_result'->'dspslGdsDxdyInfo' from raw.court_doc_raw
               where case_id = %s and doc_kind = %s and jsonb_typeof(payload->'dma_result') = 'object'
               order by fetched_at desc limit 1""",
            (f"{court}-{case_no}", f"item_detail_{seq}"),
        ).fetchone()
    info0: dict[str, Any] = (row[0] if row else None) or {}
    out = [f"사건 {court} {case_no} {seq} · 문서번호 {info0.get('dspslGdsSpcfcEcdocId')}"]
    body = {"dma_dspslGdsSpecLog": {"cortOfcCd": court, "csNo": info0.get("csNo"), "dspslGdsSeq": seq,
            "orvParam": "", "dspslGdsSpcfcEcdocId": info0.get("dspslGdsSpcfcEcdocId"),
            "cortAuctnMbrsId": "NONUSER", "docFlag": "1", "dspslDxdyPbancEcdocId": ""}}  # fmt: skip
    res = dict(page.evaluate(JS_SPEC, body))
    info = (res.get("data") or {}).get("dma_dspslSpcfcInfo") or {}
    out.append(f"  ① status {res.get('status')} · scsYn {info.get('scsYn')} · {res.get('msg')}")
    if not info.get("encParam"):
        return out
    pd = base64.b64encode(json.dumps({"encParam": info["encParam"], "pspSid": "NA", "pspTkn": "NA"}).encode()).decode()
    pages: dict[int, list[dict[str, Any]]] = {}
    meta: dict[str, Any] = {}

    def on_resp(r: Any) -> None:
        u = r.url.split("?")[0]
        if "getpdf" in u.lower():
            try:
                meta["tok"] = (json.loads(r.body()).get("data") or {}).get("accessToken")
            except Exception:  # noqa: BLE001
                pass
        if "/streamdocs/v4/documents/" in u:
            meta["sid"] = u.split("/streamdocs/v4/documents/")[1].split("/")[0]
        if "/streamdocs/v4/documents/" not in u:
            return
        try:
            if "/texts/" in u:
                pages[int(u.rsplit("/", 1)[1])] = json.loads(r.body())
            elif u.endswith("/document"):
                raw = r.body().decode("utf-8", "replace")
                meta["layout"] = len(json.JSONDecoder().raw_decode(raw[raw.find("{"):])[0].get("layout") or [])
        except Exception as e:  # noqa: BLE001
            out.append(f"  읽기 실패 {u.rsplit('/', 2)[-2:]} {type(e).__name__}")

    v = browser.new_page()
    v.on("response", on_resp)
    v.goto(f"{info['url']}?paramData={pd}", timeout=60000)
    for _ in range(40):  # 쪽마다 글이 다 올 때까지(최대 20초)
        v.wait_for_timeout(500)
        if meta.get("layout") and len(pages) >= meta["layout"]:
            break
    # 화면에 안 보인 쪽은 뷰어가 글을 안 부를 수 있음 → 틀을 끝까지 내려 봄
    if meta.get("layout") and len(pages) < meta["layout"]:
        for fr in v.frames:
            if "pvo." in fr.url:
                for _ in range(meta["layout"] * 3):
                    fr.evaluate("window.scrollBy(0, 1500); document.querySelectorAll('*').forEach(e=>{if(e.scrollHeight>e.clientHeight+50){e.scrollTop+=1500}})")
                    v.wait_for_timeout(400)
    # 11/27: 원본 PDF 를 받는 주소 찾기 — 뷰어 틀(pvo) 안에서 몇 주소를 물어 봄(법원경매정보 한도와 따로)
    sid, tok = meta.get("sid"), meta.get("tok")
    for fr in v.frames:
        if "pvo." in fr.url and sid:
            res = fr.evaluate(
                """async ([sid, tok]) => { const out = [];
                  for (const tail of ['/file', '/download', '/original', '/pdf', '/source', '', '/file?type=pdf']) {
                    for (const auth of [false, true]) { if (auth && !tok) continue;
                      try { const r = await fetch('/streamdocs/v4/documents/' + sid + tail,
                              { headers: auth ? { Authorization: 'Bearer ' + tok } : {} });
                        const b = new Uint8Array(await r.arrayBuffer());
                        out.push([tail, auth, r.status, r.headers.get('content-type'), b.length,
                                  String.fromCharCode(...b.slice(0, 8))]);
                      } catch (e) { out.push([tail, auth, 'err', String(e).slice(0, 60)]); } } }
                  return out; }""",
                [sid, tok],
            )
            for row in res:
                out.append(f"  원본 시험 {row}")
            break
    v.close()
    segs = [list(w) for w in words_from_texts(pages)]
    out.append(f"  ② 쪽 {meta.get('layout')} 중 글 받은 쪽 {sorted(pages)} · 조각 {len(segs)}")
    name = f"probe_spec_{court}_{case_no}_{seq}.json"
    (LOGS / name).write_text(json.dumps(segs, ensure_ascii=False), encoding="utf-8")
    out.append(f"  → {name}")
    return out


def main() -> None:
    from playwright.sync_api import sync_playwright

    a = sys.argv[1:]
    targets = [(a[i], a[i + 1], int(a[i + 2])) for i in range(0, len(a) - 2, 3)]
    out: list[str] = []
    with sync_playwright() as p:
        browser = launch_chrome(p)
        page = browser.new_page()
        page.goto(CASE_PAGE, wait_until="networkidle", timeout=60000)
        for court, case_no, seq in targets:
            try:
                out += one(browser, page, court, case_no, seq)
            except Exception as e:  # noqa: BLE001
                out.append(f"사건 {court} {case_no} {seq} 실패 {type(e).__name__}: {str(e)[:200]}")
            page.wait_for_timeout(6000)
        browser.close()
    LOGS.mkdir(exist_ok=True)
    (LOGS / "probe_spec.log").write_text("\n".join(out), encoding="utf-8")
    print("\n".join(out))


if __name__ == "__main__":
    main()
