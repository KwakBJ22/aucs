"""올린 등기부 원본 지우기: 매각기일 + 30일(delete_after)이 지난 PDF 칸을 비움. 읽어 낸 권리는 남김.
오류 기록(ops.errors)도 90일 지난 것은 지움(10/29).

uv run python -m aucs_workers.jobs.purge
"""

from aucs_workers.db import connect
from aucs_workers.jobs.runlog import run


def main() -> None:
    with connect() as conn, run(conn, "purge", "올린 등기부 원본 지우기") as job:
        cur = conn.execute(
            "update app.uploaded_registries set pdf = null where pdf is not null and delete_after < current_date"
        )
        job.count = cur.rowcount
        old = conn.execute("delete from ops.errors where at < now() - interval '90 days'").rowcount
        conn.commit()
    print(f"오래된 오류 기록 지움 {old}건")
    print(f"원본 지움 {job.count}건")


if __name__ == "__main__":
    main()
