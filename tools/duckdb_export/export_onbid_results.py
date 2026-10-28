"""받아 둔 공매 입찰결과(DuckDB 「참고_공매낙찰_온비드」, 개찰 5/4~9/2, 전국 133,071행) → core.onbid_results 한 번 옮기기.
API 로 받는 결과(source='api')와 같은 표, 같은 열쇠(물건관리번호·개찰일시·공고번호)라 겹치면 API 쪽이 이김.

uv run --with duckdb python tools/duckdb_export/export_onbid_results.py
"""

import os
from pathlib import Path

import duckdb
import psycopg
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")
SOURCE = "낙찰가DB_20261012"

duck = duckdb.connect(os.getenv("AUCTION_DB", "D:/Auction/duckdb/data.duckdb"), read_only=True)
rows = duck.execute(
    """
    select 물건관리번호, strptime(left(개찰일, 12), '%Y%m%d%H%M')::timestamp, coalesce(공고번호, ''), 물건번호,
           재산유형, 처분방식, 용도대, 용도중, 용도소, 물건명, split_part(물건명, ' ', 1),
           토지면적, 건물면적, nullif(감정가, 0), nullif(최저입찰가, 0), nullif(낙찰가, 0), 유찰회차,
           유효응찰자수, 무효응찰자수,
           case when 상태 = '낙찰' then nullif(감정가대비낙찰가율, 0) end,
           case when 상태 = '낙찰' then nullif(최저가대비낙찰가율, 0) end,
           상태
    from 참고_공매낙찰_온비드
    where 물건관리번호 is not null and regexp_matches(개찰일, '^20[0-9]{10}')
    qualify row_number() over (partition by 물건관리번호, left(개찰일, 12), coalesce(공고번호, '')
                               order by (상태 = '낙찰') desc, 낙찰가 desc nulls last) = 1
    """
).fetchall()
COLS = (
    "mng_no, opened_at, notice_no, item_seq, kind_name, disposal, usage_l, usage_m, usage_s, title, sido, "
    "land_m2, building_m2, appraisal_krw, min_price_krw, win_krw, failed_round, bidders, invalid_bidders, "
    "rate_appraisal, rate_min, result, source"
)
with psycopg.connect(os.environ["DATABASE_URL"]) as pg, pg.cursor() as cur:
    cur.execute("create temp table _r (like core.onbid_results including defaults) on commit drop")
    with cur.copy(f"copy _r ({COLS}) from stdin") as cp:
        for r in rows:
            cp.write_row((*r, SOURCE))
    # 개찰일시는 한국 시각으로 적혀 있음
    cur.execute(
        "update _r set opened_at = (opened_at at time zone 'UTC') at time zone 'Asia/Seoul'"
    )
    cur.execute(
        f"insert into core.onbid_results ({COLS}) select {COLS} from _r "
        "on conflict (mng_no, opened_at, notice_no) do nothing"
    )
    n = cur.rowcount
print(f"공매 입찰결과 {len(rows):,}줄 중 {n:,}줄 옮김 (source={SOURCE})")
