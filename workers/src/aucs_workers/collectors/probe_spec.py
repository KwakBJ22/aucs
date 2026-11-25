"""매각물건명세서 원본이 어떻게 오는지 한 건 보기(11/26 지시 1126a) — DB 에 안 넣음, logs/probe_spec.log.

법원 화면(11/26 06시 확인): 물건상세 「매각물건명세서」 →
  ① courtauction POST /pgj/pgj15B/insertDspslGdsSpecArtcWdrwInf.on (dspslGdsSpcfcEcdocId) → 뷰어 주소 + encParam
  ② ecfs.scourt.go.kr 문서뷰어(websquare, paramData = base64 {"encParam","pspSid":"NA","pspTkn":"NA"})
     → selectDocVwrInf.on → getPdf.on(streamdocsId) → pvo.scourt.go.kr/streamdocs 틀에서 그림
이 스크립트는 ②에서 오가는 응답(주소 · 형식 · 크기)과 틀 안 글을 적음.

    uv run python -m aucs_workers.collectors.probe_spec B000210 2025타경103942 1
"""

import base64
import json
import sys
import time
from pathlib import Path
from typing import Any

from aucs_workers.collectors.browser import launch_chrome
from aucs_workers.collectors.court_docs import CASE_PAGE, JS_POST, internal_no
from aucs_workers.collectors.polite import Polite
from aucs_workers.db import connect

LOG = Path(__file__).resolve().parents[4] / "logs" / "probe_spec.log"


def main() -> None:
    from playwright.sync_api import sync_playwright

    court, case_no, seq = sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 1
    with connect() as conn:
        row = conn.execute(
            """select payload from raw.court_doc_raw where case_id = %s and doc_kind = %s
               and jsonb_typeof(payload->'dma_result') = 'object' order by fetched_at desc limit 1""",
            (f"{court}-{case_no}", f"item_detail_{seq}"),
        ).fetchone()
    ecdoc = ""
    if row:
        s = json.dumps(row[0])
        k = s.find("dspslGdsSpcfcEcdocId")
        if k >= 0:
            ecdoc = s[k:].split('"')[2]
    out: list[str] = [f"사건 {court} {case_no} {seq} · 문서번호 {ecdoc or '없음'}"]
    polite = Polite(hourly=False)
    with sync_playwright() as p:
        browser = launch_chrome(p)
        page = browser.new_page()
        page.goto(CASE_PAGE, wait_until="networkidle", timeout=60000)
        body = {"dma_dspslGdsSpecLog": {"cortOfcCd": court, "csNo": internal_no(case_no),
                "dspslGdsSeq": seq, "orvParam": "", "dspslGdsSpcfcEcdocId": ecdoc,
                "cortAuctnMbrsId": "NONUSER", "docFlag": "1", "dspslDxdyPbancEcdocId": ""}}  # fmt: skip
        res: dict[str, Any] = polite.call(
            lambda: dict(page.evaluate(JS_POST, ["/pgj/pgj15B/insertDspslGdsSpecArtcWdrwInf.on", body])),
            "명세서 열기",
        )
        info = (res.get("data") or {}).get("dma_dspslSpcfcInfo") or {}
        out.append(f"① 답 칸: {sorted(info)} · scsYn={info.get('scsYn')} · encParam 길이 {len(info.get('encParam') or '')}")
        if not info.get("encParam"):
            out.append(f"   encParam 없음 — 답 전체 앞부분: {json.dumps(res, ensure_ascii=False)[:600]}")
        else:
            pd = base64.b64encode(json.dumps({"encParam": info["encParam"], "pspSid": "NA", "pspTkn": "NA"}).encode()).decode()
            seen: list[str] = []

            def on_resp(r: Any) -> None:
                u = r.url.split("?")[0]
                if "scourt.go.kr" in u and not u.endswith((".js", ".css", ".png", ".gif", ".svg", ".woff", ".woff2", ".xml", ".wq")):
                    try:
                        ln = len(r.body())
                    except Exception:  # noqa: BLE001
                        ln = -1
                    seen.append(f"   {r.request.method} {u} · {r.headers.get('content-type', '')} · {ln}B")

            v = browser.new_page()
            v.on("response", on_resp)
            v.goto(f"{info['url']}?paramData={pd}" if "?" not in info["url"] else f"{info['url']}&paramData={pd}", timeout=60000)
            time.sleep(12)
            out.append("② 뷰어에서 오간 것:")
            out += seen[:60]
            for fr in v.frames:
                if "streamdocs" in fr.url:
                    try:
                        txt = fr.evaluate("document.body ? document.body.innerText : ''")
                    except Exception as e:  # noqa: BLE001
                        txt = f"(못 읽음 {e})"
                    out.append(f"③ streamdocs 틀 글 {len(txt)}자:\n{txt[:3000]}")
        browser.close()
    LOG.parent.mkdir(exist_ok=True)
    LOG.write_text("\n".join(out), encoding="utf-8")
    print("\n".join(out[:5]))


if __name__ == "__main__":
    main()
