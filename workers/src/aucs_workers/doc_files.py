"""법원 서류 원본 보관(11/27 대표님): 매각물건명세서 · 현황조사서 → Storage court-docs(비공개) + core.doc_files.

법원 수집기(court_spec · court_docs)와 관리자 「명세서 올리기」가 같이 씀. 같은 파일(sha256)은 한 번만.
    save_file(conn, case_id, item_no, "spec", "court", pdf_bytes, sale_date=..., written_on=...)
"""

import hashlib
from datetime import date
from typing import Any

import psycopg

from aucs_workers.photos import client, safe_name

BUCKET = "court-docs"
EXT = {"application/pdf": "pdf", "text/html": "html", "application/json": "json"}


def save_file(
    conn: psycopg.Connection, case_id: str, item_no: int | None, kind: str, source: str,
    data: bytes, *, mime: str = "application/pdf", sale_date: date | None = None,
    written_on: date | None = None, pages: int | None = None,
) -> dict[str, Any]:  # fmt: skip
    """올렸으면 {"saved": True, "path"}, 이미 있으면 {"saved": False, "path"}, 못 올렸으면 {"saved": False, "error"}."""
    sha = hashlib.sha256(data).hexdigest()
    old = conn.execute(
        "select path from core.doc_files where case_id = %s and kind = %s and sha256 = %s",
        (case_id, kind, sha),
    ).fetchone()
    if old:
        return {"saved": False, "path": old[0] if isinstance(old, tuple) else old["path"]}
    c = client()
    if not c:
        return {"saved": False, "error": "SUPABASE_URL · SUPABASE_SECRET_KEY 없음"}
    path = f"{kind}/{safe_name(case_id)}/{item_no or 0}-{sha[:12]}.{EXT.get(mime, 'bin')}"
    r = c.post(f"/object/{BUCKET}/{path}", content=data,
               headers={"Content-Type": mime, "x-upsert": "true"})  # fmt: skip
    if r.status_code >= 300:
        return {"saved": False, "error": f"Storage {r.status_code}"}
    conn.execute(
        """insert into core.doc_files (case_id, item_no, kind, source, path, sha256, written_on, sale_date, pages, bytes)
           values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) on conflict (case_id, kind, sha256) do nothing""",
        (case_id, item_no, kind, source, path, sha, written_on, sale_date, pages, len(data)),
    )
    return {"saved": True, "path": path}
