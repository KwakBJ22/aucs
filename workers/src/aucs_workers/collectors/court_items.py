"""법원 경매 물건 수집 (서울·경기·인천 16개 법원, 앞으로 6주치 — 인천은 11/4 더함).

uv run python -m aucs_workers.collectors.court_items --test   # 서울중앙 1곳
uv run python -m aucs_workers.collectors.court_items          # 전체
"""

import argparse
from datetime import date, datetime, timedelta

import psycopg

from aucs_workers.collectors.court_site import COURTS, fetch_pages
from aucs_workers.collectors.polite import Polite
from aucs_workers.collectors.store import save_items, save_raw
from aucs_workers.db import connect
from aucs_workers.jobs.runlog import run

GONE = "gone"  # 법원 목록에서 빠짐(기일 변경·취하·정지 등). 다시 보이면 법원 상태 코드로 돌아감
GONE_MAX_SHARE = 0.2  # 한 법원에서 이보다 많이 빠지면 수집 이상으로 보고 표시하지 않음


def mark_gone(
    conn: psycopg.Connection, court: str, d_from: date, d_to: date, started: datetime
) -> int:
    """이번 수집 기간(d_from~d_to)에 있어야 하는데 법원 목록에 안 나온 물건 표시.
    공고 전 다음 회차(preview, 기일내역으로 미리 안 것)는 아직 목록에 없는 게 맞으므로 빼고 봄(11/4)."""
    row = conn.execute(
        """select count(*), count(*) filter (where i.checked_at < %s)
           from core.items i join core.cases c using (case_id)
           where c.court_code = %s and i.sale_date between %s and %s
             and i.status_code is distinct from 'preview'""",
        (started, court, d_from, d_to),
    ).fetchone()
    total, missing = row if row else (0, 0)
    if not missing:
        return 0
    if missing > total * GONE_MAX_SHARE:
        print(f"  {COURTS[court]} 빠진 물건 {missing}/{total} — 너무 많아 표시 안 함")
        return 0
    return int(
        conn.execute(
            """update core.items i set status_code = %s, updated_at = now()
           from core.cases c
           where c.case_id = i.case_id and c.court_code = %s and i.sale_date between %s and %s
             and i.checked_at < %s and i.status_code is distinct from %s
             and i.status_code is distinct from 'preview'""",
            (GONE, court, d_from, d_to, started, GONE),
        ).rowcount
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", action="store_true", help="서울중앙 1곳만")
    ap.add_argument("--show", action="store_true", help="브라우저 창 띄우기")
    ap.add_argument("--weeks", type=int, default=6)
    ap.add_argument(
        "--court", help="이 법원 코드만(예: B000240 인천) — 새로 더한 법원 채우기(11/4)"
    )
    a = ap.parse_args()
    courts = {"B000210": COURTS["B000210"]} if a.test else COURTS
    if a.court:
        courts = {a.court: COURTS[a.court]}
    d_from = date.today()
    d_to = d_from + timedelta(weeks=a.weeks)
    with connect() as conn, run(conn, "court_items", "법원 경매 물건") as job:
        now_row = conn.execute("select now()").fetchone()
        started = now_row[0] if now_row else datetime.now().astimezone()
        seen: set[str] = set()
        for court, rows in fetch_pages(
            courts, Polite(hourly=False), results=False,
            date_from=f"{d_from:%Y%m%d}", date_to=f"{d_to:%Y%m%d}", show=a.show,
        ):  # fmt: skip
            save_raw(conn, "court_item_raw", court, rows)
            job.count += save_items(conn, rows)
            conn.commit()
            print(f"  {COURTS[court]} +{len(rows)}")
            seen.add(court)
        # 모든 법원을 끝까지 받았을 때만(중간에 멈추면 여기까지 오지 않음)
        gone = sum(mark_gone(conn, cd, d_from, d_to, started) for cd in sorted(seen))
        conn.commit()
    print(f"끝: {job.count:,}건 · 법원 목록에서 빠진 물건 {gone:,}건")


if __name__ == "__main__":
    main()
