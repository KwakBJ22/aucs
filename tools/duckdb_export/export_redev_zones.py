"""로컬 DuckDB 「정비사업_지번」의 구역 추진현황(약 500곳) → ref.redev_zones 한 번 옮기기.

uv run --with duckdb python tools/duckdb_export/export_redev_zones.py
"""

import os
from pathlib import Path

import duckdb
import psycopg
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

duck = duckdb.connect(os.getenv("AUCTION_DB", "D:/Auction/duckdb/data.duckdb"), read_only=True)
rows = duck.execute(
    "select 자치구, 이름, 사업유형, 단계, 위치, nullif(동명, ''), 본번, 부번, 최근단계일 from 정비사업_지번 where 출처 = '구역 추진현황'"
).fetchall()
with psycopg.connect(os.environ["DATABASE_URL"]) as pg, pg.cursor() as cur:
    cur.execute("delete from ref.redev_zones where source = '구역 추진현황'")
    cur.executemany(
        "insert into ref.redev_zones (source, gu, name, biz_type, stage, address, dong_name, main_no, sub_no, recent_stage_date)"
        " values ('구역 추진현황', %s, %s, %s, %s, %s, %s, %s, %s, %s)",
        rows,
    )
print(f"구역 추진현황 {len(rows):,}곳")
