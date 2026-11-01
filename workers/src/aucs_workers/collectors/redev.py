"""서울 정비사업 정보몽땅 「사업장 목록」 엑셀 받기 → ref.redev_zones (3개월마다).

    uv run python -m aucs_workers.collectors.redev            # 받고 넣기
    uv run python -m aucs_workers.collectors.redev --file 사업장목록.xls   # 받아 둔 파일로

화면의 「엑셀다운로드」 버튼을 한 번 누르는 것과 같습니다(요청 1~2번).
해산·청산·이전고시와 일시중단 사업장은 잇기 대상에서 뺍니다.
"""

import argparse
import re
from datetime import date
from pathlib import Path
from typing import Any

from aucs_workers.collectors.browser import launch_chrome
from aucs_workers.db import ROOT, connect
from aucs_workers.jobs.runlog import run

PAGE = "https://cleanup.seoul.go.kr/cleanup/bsnssttus/lscrMainIndx.do"
INBOX = ROOT.parent / "data" / "정비사업"  # 저장소 밖 받은 파일 폴더
ENDED = {"조합해산", "조합청산", "이전고시"}
_LOT = re.compile(r"^\s*([가-힣0-9]*(?:동|가|로|리))\s*(?:산\s*)?(\d+)(?:-(\d+))?")


def split_lot(text: str | None) -> tuple[str | None, int | None, int]:
    """「개포동 138」「수송동146-12」「신문로1가158」 → (동명, 본번, 부번)."""
    m = _LOT.match(text or "")
    if not m:
        return None, None, 0
    return m.group(1), int(m.group(2)), int(m.group(3) or 0)


def read_xls(path: Path) -> list[dict[str, str]]:
    import xlrd

    sh = xlrd.open_workbook(str(path)).sheet_by_index(0)
    head: list[str] | None = None
    rows = []
    for i in range(sh.nrows):
        vals = [str(v).strip() for v in sh.row_values(i)]
        if head is None:
            if "사업장명" in vals:
                head = vals
            continue
        if any(vals):
            rows.append(dict(zip(head, vals, strict=False)))
    if head is None:
        raise SystemExit(f"{path.name}: 「사업장명」 머리줄이 없습니다 — 화면이 바뀌었을 수 있음")
    return rows


def to_zone(r: dict[str, str]) -> dict[str, Any] | None:
    if r.get("진행단계") in ENDED or r.get("운영구분") == "일시중단" or not r.get("사업장명"):
        return None
    dong, main_no, sub_no = split_lot(r.get("대표지번"))
    return {"gu": r.get("자치구"), "name": r["사업장명"], "biz_type": r.get("사업구분"), "stage": r.get("진행단계"),
            "address": r.get("대표지번"), "dong_name": dong, "main_no": main_no, "sub_no": sub_no,
            "op_status": r.get("운영구분")}  # fmt: skip


def download() -> Path:
    from playwright.sync_api import sync_playwright

    INBOX.mkdir(parents=True, exist_ok=True)
    out = INBOX / f"사업장목록_{date.today():%Y%m%d}.xls"
    with sync_playwright() as p:
        browser = launch_chrome(p)
        page = browser.new_page(accept_downloads=True)
        page.goto(PAGE, wait_until="networkidle", timeout=60000)
        with page.expect_download(timeout=120000) as dl:
            page.click("a.btn_excel")
        dl.value.save_as(str(out))
        browser.close()
    if out.stat().st_size < 50_000:  # 정상 파일은 약 300KB
        raise SystemExit(
            f"받은 파일이 너무 작습니다({out.stat().st_size:,}바이트) — 화면이 바뀌었을 수 있음"
        )
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file")
    a = ap.parse_args()
    path = Path(a.file) if a.file else download()
    zones = [z for r in read_xls(path) if (z := to_zone(r))]
    with connect() as conn, run(conn, "redev", "정비사업") as job:
        conn.execute("delete from ref.redev_zones where source = '사업장 목록'")
        with conn.cursor() as cur:
            cur.executemany(
                "insert into ref.redev_zones (source, gu, name, biz_type, stage, address, dong_name, main_no, sub_no,"
                " op_status, source_date) values ('사업장 목록', %(gu)s, %(name)s, %(biz_type)s, %(stage)s, %(address)s,"
                " %(dong_name)s, %(main_no)s, %(sub_no)s, %(op_status)s, current_date)",
                zones,
            )
        job.count = len(zones)
    print(f"끝: {path.name} · 사업장 {len(zones):,}곳")


if __name__ == "__main__":
    main()
