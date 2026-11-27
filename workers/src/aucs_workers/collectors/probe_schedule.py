"""끝난 지 오래된 사건도 사건 「기일내역」에 낙찰가가 나오나 몇 건 보기(11/27) — DB 에 안 넣음, logs/probe_schedule.log.

매각결과 화면은 기일 뒤 7일만 보이지만, 사건 기일내역(selectCsDtlDxdyDts)의 dxdyRslt 에는 「매각<br />(241,510,000원)」처럼
낙찰가가 붙어 옴(진행 사건에서 확인). 종국 뒤 오래된 사건도 그런지 — 사건 하나에 법원 1번, 사건 사이 6초.

    python -m aucs_workers.collectors.probe_schedule B000240 2020타경11553 B000240 2020타경12181 B000212 2023타경6427
"""

import sys
from pathlib import Path

from aucs_workers.collectors.browser import launch_chrome
from aucs_workers.collectors.court_docs import CASE_PAGE, JS_POST, internal_no

LOGS = Path(__file__).resolve().parents[4] / "logs"


def main() -> None:
    from playwright.sync_api import sync_playwright

    a = sys.argv[1:]
    targets = [(a[i], a[i + 1]) for i in range(0, len(a) - 1, 2)]
    out: list[str] = []
    with sync_playwright() as p:
        browser = launch_chrome(p)
        page = browser.new_page()
        page.goto(CASE_PAGE, wait_until="networkidle", timeout=60000)
        for court, case_no in targets:
            try:
                body = {"dma_srchDxdyDtsLst": {"cortOfcCd": court, "csNo": internal_no(case_no)}}
                res = dict(page.evaluate(JS_POST, ["/pgj/pgj15A/selectCsDtlDxdyDts.on", body]))
                rows = (res.get("data") or {}).get("dlt_dxdyDtsLst") or []
                sold = [r for r in rows if str(r.get("dxdyRslt") or "").startswith("매각")]
                out.append(f"{court} {case_no}: ok {res.get('ok')} · status {res.get('status')} · 기일 {len(rows)}줄 · 매각 {len(sold)}줄 · {str(res.get('msg') or '')[:80]}")
                for r in rows:
                    out.append(f"   {r.get('dxdyTime')} {r.get('auctnDxdyKndNm')} 물건{r.get('dspslGdsSeq')} 최저 {r.get('tsLwsDspslPrc')} → {str(r.get('dxdyRslt') or '').replace('<br />', ' ')}")
            except Exception as e:  # noqa: BLE001
                out.append(f"{court} {case_no} 실패 {type(e).__name__}: {str(e)[:200]}")
            page.wait_for_timeout(6000)
        browser.close()
    LOGS.mkdir(exist_ok=True)
    (LOGS / "probe_schedule.log").write_text("\n".join(out), encoding="utf-8")
    print("\n".join(out))


if __name__ == "__main__":
    main()
