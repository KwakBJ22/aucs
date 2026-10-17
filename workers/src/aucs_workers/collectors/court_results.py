"""법원 매각결과 수집 (사이트가 최근 1주만 보여 주므로 매주 이상).

uv run python -m aucs_workers.collectors.court_results
"""

import argparse

from aucs_workers.collectors.court_site import COURTS, fetch_pages
from aucs_workers.collectors.polite import Polite
from aucs_workers.collectors.store import save_raw, save_results
from aucs_workers.db import connect
from aucs_workers.jobs.runlog import run


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", action="store_true", help="서울중앙 1곳만")
    ap.add_argument("--show", action="store_true")
    a = ap.parse_args()
    courts = {"B000210": COURTS["B000210"]} if a.test else COURTS
    with connect() as conn, run(conn, "court_results", "법원 매각결과") as job:
        for court, rows in fetch_pages(courts, Polite(), results=True, show=a.show):
            save_raw(conn, "court_result_raw", court, rows)
            job.count += save_results(conn, rows)
            conn.commit()
            print(f"  {COURTS[court]} +{len(rows)}")
    print(f"끝: {job.count:,}건")


if __name__ == "__main__":
    main()
