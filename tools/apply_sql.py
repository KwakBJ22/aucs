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
    # db/migrations 의 이주 파일이면 적용 기록도 남김(11/4) — deploy.bat 3단계가 이 기록으로 「다 올렸는지」를 봄
    if path.parent.name == "migrations" and path.stem[:4].isdigit():
        done = conn.execute(
            "select 1 from supabase_migrations.schema_migrations where name = %s", (path.stem,)
        ).fetchone()
        if not done:
            conn.execute(
                "insert into supabase_migrations.schema_migrations (version, name)"
                " values (to_char(now() at time zone 'utc', 'YYYYMMDDHH24MISS'), %s)",
                (path.stem,),
            )
    conn.commit()
    size = conn.execute("select pg_size_pretty(pg_database_size(current_database()))").fetchone()
print(f"적용: {path.name} · DB 크기 {size[0] if size else '?'}")
