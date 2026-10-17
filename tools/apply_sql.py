"""SQL 파일 하나를 DB에 적용합니다 (대표님 PC에서). 사용: uv run python tools/apply_sql.py <파일>"""

import os
import sys
from pathlib import Path

import psycopg
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

path = Path(sys.argv[1])
sql = path.read_text(encoding="utf-8")
with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
    conn.execute(sql)
    conn.commit()
    size = conn.execute("select pg_size_pretty(pg_database_size(current_database()))").fetchone()
print(f"적용: {path.name} · DB 크기 {size[0] if size else '?'}")
