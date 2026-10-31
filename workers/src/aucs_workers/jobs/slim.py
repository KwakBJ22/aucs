"""원문 줄이기(11/1, 한 번): 법원 원문 속 사진(base64) 때문에 raw.court_doc_raw 가 6GB → DB가 꽉 참(10/31 아침 묶음 멈춤).

1) 진행 중(또는 매각 뒤 30일 안) 사건: 사진을 휴대폰 크기로 줄여 Storage 로 옮기고 원문에서 뺌
2) 나머지(끝난 사건): 사진 글자만 DB 안에서 바로 뺌(raw.strip_pics)
3) 표를 다시 써서(VACUUM FULL) 빈자리를 돌려받음
여러 번 돌려도 됨(이미 뺀 줄은 건너뜀).

    uv run python -m aucs_workers.jobs.slim
"""

from datetime import date, timedelta

from psycopg.types.json import Jsonb

from aucs_workers.db import connect
from aucs_workers.jobs.runlog import run
from aucs_workers.photos import pull_pics, store

BIG = 100_000  # 이보다 큰 원문 줄 = 사진이 들어 있음

ROWS_SQL = """
select r.raw_id, r.case_id,
       exists (select 1 from core.items i where i.case_id = r.case_id and i.sale_date >= %s) as live
from raw.court_doc_raw r
where r.doc_kind like 'item_detail_%%' and pg_column_size(r.payload) > %s
order by r.raw_id
"""


def main() -> None:
    keep_from = date.today() - timedelta(days=30)
    with connect() as conn, run(conn, "slim", "원문 사진 빼기") as job:
        conn.execute("set statement_timeout = 0")
        rows = conn.execute(ROWS_SQL, (keep_from, BIG)).fetchall()
        live = [(rid, cid) for rid, cid, lv in rows if lv]
        dead = [rid for rid, _, lv in rows if not lv]
        print(
            f"사진 든 원문 {len(rows):,}줄 · 진행 중 {len(live):,} · 끝난 사건 {len(dead):,}",
            flush=True,
        )
        photos = 0
        for n, (rid, cid) in enumerate(live, 1):
            row = conn.execute(
                "select payload from raw.court_doc_raw where raw_id = %s", (rid,)
            ).fetchone()
            if not row:
                continue
            slim, pics = pull_pics(row[0])
            photos += store(conn, cid, pics)
            conn.execute(
                "update raw.court_doc_raw set payload = %s where raw_id = %s", (Jsonb(slim), rid)
            )
            conn.commit()
            if n % 50 == 0:
                print(f"  진행 중 {n:,}/{len(live):,} · 사진 {photos:,}장", flush=True)
        for i in range(0, len(dead), 50):
            conn.execute("update raw.court_doc_raw set payload = raw.strip_pics(payload) where raw_id = any(%s)",
                         (dead[i : i + 50],))  # fmt: skip
            conn.commit()
            if (i // 50) % 10 == 0:
                print(f"  끝난 사건 {min(i + 50, len(dead)):,}/{len(dead):,}", flush=True)
        job.count = len(rows)
        print(f"사진 {photos:,}장 옮김", flush=True)
    # 빈자리 돌려받기: VACUUM FULL 은 묶음(transaction) 밖에서만 됨
    with connect() as c2:
        c2.autocommit = True
        c2.execute("set statement_timeout = 0")
        before = c2.execute(
            "select pg_size_pretty(pg_database_size(current_database()))"
        ).fetchone()
        print(f"표 다시 쓰는 중(몇 분)... DB {before[0] if before else '?'}", flush=True)
        c2.execute("vacuum full raw.court_doc_raw")
        after = c2.execute("select pg_size_pretty(pg_database_size(current_database()))").fetchone()
        print(f"끝: DB {after[0] if after else '?'}", flush=True)


if __name__ == "__main__":
    main()
