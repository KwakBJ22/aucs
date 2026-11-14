"""대표님이 받아 둔 감정평가서 원본(PDF) 폴더 → raw 'appraisal_pdf' (11/11 대표님 — 원본은 따로 받기로).

폴더의 PDF 를 읽어 회사 이름 · 쪽수 · 앞부분 글 · 요항표를 남깁니다(kapa_pdf 와 같은 꼴, PDF 자체는 저장하지 않음).
어느 사건인지는 ① 글 속 사건번호(「2025타경56683」) ② 파일 이름 = 감정서 번호(법원 감정평가서 정보) 순으로 찾습니다.
법원 · KAPA 에 접속하지 않습니다. 같은 파일(이름만 다른 복사본)은 한 번만.
11/11 대표님: 원본 PDF 를 손님이 열어 보게 Storage(appraisal-pdfs)에 올리고 core.appraisal_files 에 적음(이미 올린 사건은 건너뜀).

    cd D:\\Auction\\auction-platform\\workers
    uv run python -m aucs_workers.collectors.appraisal_folder D:\\Auction\\감정평가서
    uv run python -m aucs_workers.collectors.appraisal_folder D:\\Auction\\감정평가서 --court B000250   # 법원을 못 박을 때

받은 폴더(11/14 대표님 — 받아만 두면 알아서): 「관리자_요청」 작업(5분마다)이 inbox() 를 불러 폴더 맨 위의 새 PDF 를 넣고,
넣은 것은 「넣음」, 못 넣은 것은 「못 넣음」 폴더로 옮깁니다(폴더가 비어 있으면 다 된 것). 못 넣은 파일은 이름을
사건번호(「2025타경12345.pdf」)로 바꿔 다시 두면 됩니다. 폴더는 .env 의 APPRAISAL_INBOX(없으면 D:\\Auction\\감정평가서).
"""

import argparse
import hashlib
import os
import re
import time
from pathlib import Path
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from aucs_workers.collectors.parse import checksum
from aucs_workers.db import connect
from aucs_workers.extract.appraisal_pdf import case_numbers, read_pdf
from aucs_workers.jobs.runlog import run
from aucs_workers.photos import client, safe_name

BUCKET = "appraisal-pdfs"
INBOX = r"D:\Auction\감정평가서"  # 받은 폴더 기본 자리(.env APPRAISAL_INBOX 로 바꿈)
DONE, MISS = "넣음", "못 넣음"


def upload(conn: psycopg.Connection, case_id: str, data: dict[str, Any], raw: bytes) -> bool:
    """원본 PDF 를 Storage 에 올리고 core.appraisal_files 에 적음. 이미 있으면 건너뜀. 올렸으면 True."""
    if conn.execute("select 1 from core.appraisal_files where case_id = %s", (case_id,)).fetchone():
        return False
    c = client()
    if not c:
        print("   [원본] .env 의 SUPABASE_URL·SUPABASE_SECRET_KEY 가 비어 원본을 올리지 못함")
        return False
    path = f"{safe_name(case_id)}.pdf"
    r = c.post(f"/object/{BUCKET}/{path}", content=raw,
               headers={"Content-Type": "application/pdf", "x-upsert": "true"})  # fmt: skip
    if r.status_code >= 300:
        print(f"   [원본] {case_id} 올리기 실패 {r.status_code}")
        return False
    conn.execute(
        """insert into core.appraisal_files (case_id, appraisal_no, path, firm, pages, bytes)
           values (%s,%s,%s,%s,%s,%s) on conflict (case_id) do nothing""",
        (case_id, data.get("no"), path, data.get("firm"), data.get("pages"), len(raw)),
    )
    conn.commit()
    return True


def appraisal_no(path: Path) -> str:
    """파일 이름 → 감정서 번호(「2025-1-049 (2).pdf」의 복사 꼬리는 뗌)."""
    return re.sub(r"\s*\(\d+\)$", "", path.stem).strip()


def find_case(
    conn: psycopg.Connection, data: dict[str, Any], no: str, court: str | None
) -> list[str]:
    """이 PDF 의 사건 — 글 속 사건번호로, 없으면 감정서 번호로. 여러 법원에 같은 번호가 있으면 모두 돌려줌(그때는 넣지 않음)."""
    # 글 속 사건번호 → 파일 이름에 적은 사건번호(못 넣은 파일을 손으로 맞출 때, 11/14)
    for cs in [
        *case_numbers(str(data.get("head") or "")),
        *case_numbers(str(data.get("file") or "")),
    ]:
        rows = conn.execute(
            "select distinct case_id from core.items where case_id like %s and (%s::text is null or case_id like %s)",
            (f"%-{cs}", court, f"{court}-%"),
        ).fetchall()
        if rows:
            return [r[0] for r in rows]
    rows = conn.execute(
        """select distinct case_id from raw.court_doc_raw
           where doc_kind = 'appraisal' and payload -> 'info' ->> 'aeeWevlNo' = %s""",
        (no,),
    ).fetchall()
    if (
        not rows
    ):  # 그림 PDF 처럼 글이 없으면 — 전에 이 파일 이름으로 넣어 둔 사건(11/11 손으로 맞춘 것 포함)
        rows = conn.execute(
            """select distinct case_id from raw.court_doc_raw
               where doc_kind = 'appraisal_pdf' and payload ->> 'no' = %s""",
            (no,),
        ).fetchall()
    return [r[0] for r in rows]


def ingest(conn: psycopg.Connection, f: Path, court: str | None = None) -> tuple[str | None, str]:
    """PDF 하나를 넣음 → (사건, 한 줄). 못 넣으면 사건은 None 이고 한 줄은 까닭."""
    raw = f.read_bytes()
    no = appraisal_no(f)
    try:
        data = {"no": no, "from": "folder", **read_pdf(raw)}
    except Exception as e:  # noqa: BLE001 — 깨진 PDF 는 건너뜀
        return None, f"못 읽음 {type(e).__name__}"
    cases = find_case(conn, {**data, "file": f.stem}, no, court)
    if len(cases) != 1:
        return None, "사건 못 찾음" if not cases else "법원 여럿 " + ", ".join(cases)
    conn.execute(
        "insert into raw.court_doc_raw (case_id, doc_kind, payload, checksum) values (%s,'appraisal_pdf',%s,%s) on conflict do nothing",
        (cases[0], Jsonb(data), checksum(data)),
    )
    conn.commit()
    up = upload(conn, cases[0], data, raw)
    if (
        not up
        and not conn.execute(
            "select 1 from core.appraisal_files where case_id = %s", (cases[0],)
        ).fetchone()
    ):
        return None, "원본 올리기 실패"
    return cases[0], (
        f"{data['firm'] or '회사 이름 못 찾음'} · {data['pages']}쪽 · 요항 {len(data['points'])}칸"
        + (" · 그림 PDF(글 없음)" if data["scanned"] else "")
        + (" · 원본 올림" if up else "")
    )


def _move(f: Path, to: Path) -> None:
    """파일을 아래 폴더로 옮김(같은 이름이 있으면 시각을 붙임). 지우지 않음."""
    to.mkdir(exist_ok=True)
    t = to / f.name
    if t.exists():
        t = to / f"{f.stem}-{int(time.time())}{f.suffix}"
    f.rename(t)


def inbox(folder: str | None = None) -> str | None:
    """받은 폴더(5분마다): 새 PDF 를 넣고 「넣음」·「못 넣음」으로 옮김. 한 줄 결과, 할 일이 없으면 None."""
    root = Path(folder or os.getenv("APPRAISAL_INBOX", "").strip() or INBOX)
    if not root.is_dir():
        return None
    now = time.time()
    files = [
        f
        for f in sorted(root.iterdir())
        if f.is_file() and f.suffix.lower() == ".pdf" and now - f.stat().st_mtime > 15
    ]  # 방금 바뀐 파일은 받는 중일 수 있어 다음 차례에
    if not files:
        return None
    miss: list[str] = []
    with connect() as conn, run(conn, "appraisal_inbox", "감정평가서 받은 폴더") as job:
        for f in files:
            try:
                case, line = ingest(conn, f)
            except Exception as e:  # noqa: BLE001 — 한 파일 탈이 나머지를 막지 않게(다시 두면 다시 해 봄)
                conn.rollback()
                case, line = None, f"오류 {type(e).__name__}"
            _move(f, root / (DONE if case else MISS))
            if case:
                job.count += 1
            else:
                miss.append(f"{f.name}({line})")
            print(f"   {f.name} → {case or '못 넣음'} · {line}", flush=True)
        msg = f"{root} · 넣음 {job.count}" + (
            f" · 못 넣음 {len(miss)}: {', '.join(miss)}" if miss else ""
        )
        conn.execute(
            "update ops.job_runs set message = %s where run_id = %s", (msg[:500], job.run_id)
        )
        conn.commit()
    return msg


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--court", help="법원 코드(같은 사건번호가 여러 법원에 있을 때)")
    a = ap.parse_args()
    seen: set[str] = set()
    miss: list[str] = []
    with connect() as conn, run(conn, "appraisal_folder", "감정평가서 폴더") as job:
        for f in sorted(Path(a.folder).glob("*.pdf")):
            h = hashlib.md5(f.read_bytes()).hexdigest()  # noqa: S324 — 같은 파일 가리기용
            if h in seen:
                continue
            seen.add(h)
            case, line = ingest(conn, f, a.court)
            if not case:
                miss.append(f"{f.name} ({line})")
                continue
            job.count += 1
            print(f"   {case} {line}")
    print(f"끝: {job.count}건" + (f" · 못 넣은 것 {len(miss)}건" if miss else ""))
    for m in miss:
        print(f"   - {m}")


if __name__ == "__main__":
    main()
