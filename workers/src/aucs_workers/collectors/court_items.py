"""법원 경매 물건 수집 (서울·경기 15개 법원, 앞으로 6주치).

uv run python -m aucs_workers.collectors.court_items --test   # 서울중앙 1곳
uv run python -m aucs_workers.collectors.court_items          # 전체
"""

import argparse
from datetime import date, timedelta

from aucs_workers.collectors.court_site import COURTS, fetch_pages
from aucs_workers.collectors.polite import Polite
from aucs_workers.collectors.store import save_items, save_raw
from aucs_workers.db import connect
from aucs_workers.jobs.runlog import run


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", action="store_true", help="서울중앙 1곳만")
    ap.add_argument("--show", action="store_true", help="브라우저 창 띄우기")
    ap.add_argument("--weeks", type=int, default=6)
    a = ap.parse_args()
    courts = {"B000210": COURTS["B000210"]} if a.test else COURTS
    d_from = date.today()
    d_to = d_from + timedelta(weeks=a.weeks)
    with connect() as conn, run(conn, "court_items", "법원 경매 물건") as job:
        for court, rows in fetch_pages(
            courts, Polite(), results=False,
            date_from=f"{d_from:%Y%m%d}", date_to=f"{d_to:%Y%m%d}", show=a.show,
        ):  # fmt: skip
            save_raw(conn, "court_item_raw", court, rows)
            job.count += save_items(conn, rows)
            conn.commit()
            print(f"  {COURTS[court]} +{len(rows)}")
    print(f"끝: {job.count:,}건")


if __name__ == "__main__":
    main()
