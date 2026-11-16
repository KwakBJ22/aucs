"""지우기(아침 묶음 마지막) — 11/4 대표님: 법이 강제하지 않으면 아무것도 지우지 않음(용량은 따로 풀 문제).

남겨 둠(11/4부터): 법원 원문(raw.court_doc_raw) · 현장 사진 · 오류 기록.

법 때문에 지우는 것만:
- (11/17 대표님: 올린 등기부 원본 PDF 는 지우기를 확인한 뒤 정할 일 — 확인될 때까지 지우지 않음. delete_after 칸은 그대로 둠)
- 끝난 사건 실명: 사건의 모든 물건이 매각기일 + 30일 지남 → 임차인·권리자 실명(name_raw·holder_raw)·원문 발췌 비움
  (개인정보 보호법 제21조 — 처리 목적을 이룬 개인정보는 지체 없이 파기). 가린 이름·날짜·금액·위험 신호·낙찰 결과는 남김.

uv run python -m aucs_workers.jobs.purge
"""

from datetime import date, timedelta

from aucs_workers.db import connect
from aucs_workers.jobs.runlog import run

CLOSED_SQL = """
select c.case_id from core.cases c
where exists (select 1 from core.items i where i.case_id = c.case_id)
  and not exists (select 1 from core.items i where i.case_id = c.case_id
                  and (i.sale_date is null or i.sale_date >= %(cut)s))
  and (exists (select 1 from core.tenants t where t.case_id = c.case_id and t.name_raw is not null)
       or exists (select 1 from core.rights x where x.case_id = c.case_id and x.holder_raw is not null))
"""


def main() -> None:
    """끝난 사건 실명만 비움 — 법원 원문·사진 · 올린 등기부 원본은 남김(11/4, 11/17)."""
    cut = date.today() - timedelta(days=30)
    with connect() as conn, run(conn, "purge", "끝난 사건 실명 비우기") as job:
        closed = [r[0] for r in conn.execute(CLOSED_SQL, {"cut": cut}).fetchall()]
        job.count = len(closed)
        for i in range(0, len(closed), 200):
            part = closed[i : i + 200]
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
    print(
        f"끝난 사건 {len(closed):,}건 실명 비움 (원문 · 사진 · 올린 등기부 원본은 남김)"
    )


if __name__ == "__main__":
    main()
