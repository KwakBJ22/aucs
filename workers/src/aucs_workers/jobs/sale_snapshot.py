"""낙찰 순간 기록(11/21 대표님 「작업해」) → analysis.sale_snapshots.

    uv run python -m aucs_workers.jobs.sale_snapshot            # 최근 30일 매각기일(아침 묶음)
    uv run python -m aucs_workers.jobs.sale_snapshot --all      # 처음 한 번 — 쌓인 매각결과 전부

- 매각결과(core.sale_results)마다 입찰일 0시(한국 시각) 전에 만든 마지막 분석을 통째로 얼려 둠.
  분석은 나중에 다시 돌면 바뀌므로(시세에 낙찰 뒤 거래가 들어가는 등) 그때 값이 따로 있어야 요인을 정직하게 잴 수 있음.
- 입찰일 전 분석이 없는 결과는 넣지 않음(나중에 만든 분석으로 대신하지 않음).
- 한 번 넣은 줄은 바꾸지 않음(on conflict do nothing) — 몇 번 돌려도 같음.
"""

import argparse
from datetime import date, timedelta

from aucs_workers.db import connect
from aucs_workers.jobs.runlog import run

SQL = """
insert into analysis.sale_snapshots (
  item_id, sale_date, result, court_code, case_no, item_no, usage_name, building_area_m2,
  appraisal_krw, min_price_krw, winning_bid_krw, sale_rate, failed_count, is_share, is_special_case,
  analysis_version, analysis_at, engine_version, analysis)
select s.item_id, s.sale_date, s.result, s.court_code, s.case_no, s.item_no, s.usage_name,
       s.building_area_m2, s.appraisal_krw, s.min_price_krw, s.winning_bid_krw, s.sale_rate,
       s.failed_count, s.is_share, s.is_special_case,
       a.version, a.computed_at, a.engine_version, a.result
from core.sale_results s
join lateral (
  select version, computed_at, engine_version, result from analysis.item_analysis a
  where a.item_id = s.item_id and a.computed_at < (s.sale_date::timestamp at time zone 'Asia/Seoul')
  order by a.version desc limit 1
) a on true
where s.item_id is not null and s.result in ('sold', 'failed') and s.sale_date >= %s
on conflict (item_id, sale_date) do nothing
"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="쌓인 매각결과 전부(처음 한 번)")
    a = ap.parse_args()
    since = date(2000, 1, 1) if a.all else date.today() - timedelta(days=30)
    with connect() as conn, run(conn, "sale_snapshot", "낙찰 순간 기록") as job:
        conn.execute("set statement_timeout = 0")
        n = conn.execute(SQL, (since,)).rowcount
        job.count = n
        conn.commit()
    print(f"낙찰 순간 기록: 새로 {n:,}줄 (매각기일 {since} 부터)", flush=True)


if __name__ == "__main__":
    main()
