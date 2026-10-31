"""지우기(아침 묶음 마지막):
- 올린 등기부 원본: 매각기일 + 30일(delete_after)이 지난 PDF 칸을 비움. 읽어 낸 권리는 남김.
- 오류 기록(ops.errors): 90일 지난 것(10/29).
- 끝난 사건(11/1, 업계 자율규제와 같게): 사건의 모든 물건이 매각기일 + 30일 지남 →
  법원 원문(raw.court_doc_raw)·현장 사진 지우고, 임차인·권리자 실명(name_raw·holder_raw)·원문 발췌 비움.
  뽑아 둔 요약(가린 이름·날짜·금액·위험 신호·낙찰 결과)은 남김.

uv run python -m aucs_workers.jobs.purge
"""

from datetime import date, timedelta

from aucs_workers.db import connect
from aucs_workers.jobs.runlog import run
from aucs_workers.photos import remove

CLOSED_SQL = """
select c.case_id from core.cases c
where exists (select 1 from core.items i where i.case_id = c.case_id)
  and not exists (select 1 from core.items i where i.case_id = c.case_id
                  and (i.sale_date is null or i.sale_date >= %(cut)s))
  and (exists (select 1 from raw.court_doc_raw r where r.case_id = c.case_id)
       or exists (select 1 from core.item_photos p where p.case_id = c.case_id)
       or exists (select 1 from core.tenants t where t.case_id = c.case_id and t.name_raw is not null)
       or exists (select 1 from core.rights x where x.case_id = c.case_id and x.holder_raw is not null))
"""


def main() -> None:
    cut = date.today() - timedelta(days=30)
    with connect() as conn, run(conn, "purge", "올린 등기부 원본·끝난 사건 원문 지우기") as job:
        cur = conn.execute(
            "update app.uploaded_registries set pdf = null where pdf is not null and delete_after < current_date"
        )
        job.count = cur.rowcount
        old = conn.execute("delete from ops.errors where at < now() - interval '90 days'").rowcount
        conn.commit()
        closed = [r[0] for r in conn.execute(CLOSED_SQL, {"cut": cut}).fetchall()]
        docs = pics = 0
        for i in range(0, len(closed), 200):
            part = closed[i : i + 200]
            pics += remove(conn, part)
            docs += conn.execute(
                "delete from raw.court_doc_raw where case_id = any(%s)", (part,)
            ).rowcount
            conn.execute(
                "update core.tenants set name_raw = null where case_id = any(%s) and name_raw is not null",
                (part,),
            )
            conn.execute(
                "update core.rights set holder_raw = null where case_id = any(%s) and holder_raw is not null",
                (part,),
            )
            conn.execute(
                """update core.extracted_fields f set raw_text = null from core.documents d
                   where f.doc_id = d.doc_id and d.case_id = any(%s) and f.raw_text is not null""",
                (part,),
            )
            conn.commit()
    print(f"원본 지움 {job.count}건 · 오래된 오류 기록 {old}건")
    print(f"끝난 사건 {len(closed):,}건: 원문 {docs:,}줄 · 사진 {pics:,}장 지움, 실명 비움")


if __name__ == "__main__":
    main()
