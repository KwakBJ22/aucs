"""법원 현장 사진(11/1): 원문 속 사진(base64)을 휴대폰 크기로 줄여 Supabase Storage(item-photos)에 두고, 원문에서는 뺌.

- 한 사건에 사진이 30장 넘게 오기도 해서 앞에서부터 MAX장만(같은 파일 이름은 한 번).
- 가로·세로 긴 쪽 960px, JPEG 품질 72 → 한 장 수십 KB.
- 올리기가 실패해도 서류 저장은 계속(사진은 다음에 다시 받을 때 채움).
"""

import base64
import io
import logging
import os
from typing import Any

import httpx
import psycopg
from PIL import Image

from aucs_workers.db import ROOT  # noqa: F401 — .env 를 먼저 읽게

log = logging.getLogger("aucs_workers.photos")
BUCKET = "item-photos"
MAX = 12
SIDE = 960
_client: httpx.Client | None = None


def pull_pics(payload: Any) -> tuple[Any, list[tuple[str, str]]]:
    """원문에서 사진 글자를 빼고, 빼낸 것은 (파일 이름, base64) 목록으로. (순수 함수)"""
    found: list[tuple[str, str]] = []

    def walk(x: Any) -> Any:
        if isinstance(x, dict):
            if isinstance(x.get("picFile"), str):
                name = str(x.get("picTitlNm") or x.get("picFileNm") or len(found))
                found.append((name, x["picFile"]))
            return {k: walk(v) for k, v in x.items() if k != "picFile"}
        if isinstance(x, list):
            return [walk(v) for v in x]
        return x

    return walk(payload), found


def shrink(b64: str) -> tuple[bytes, int, int]:
    im = Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGB")
    im.thumbnail((SIDE, SIDE))
    out = io.BytesIO()
    im.save(out, "JPEG", quality=72, optimize=True, progressive=True)
    return out.getvalue(), im.width, im.height


def client() -> httpx.Client | None:
    global _client
    url, key = os.getenv("SUPABASE_URL", "").rstrip("/"), os.getenv("SUPABASE_SECRET_KEY", "")
    if not url or not key:
        return None
    if _client is None:
        _client = httpx.Client(base_url=f"{url}/storage/v1", timeout=60,
                               headers={"apikey": key, "Authorization": f"Bearer {key}"})  # fmt: skip
    return _client


def safe_name(case_id: str) -> str:
    return "".join(
        ch if ch.isalnum() or ch in "-_" else "_"
        for ch in case_id.encode("ascii", "ignore").decode() or "x"
    )


def store(conn: psycopg.Connection, case_id: str, pics: list[tuple[str, str]]) -> int:
    """사건 사진을 줄여 올리고 core.item_photos 에 적음. 이미 있으면 건너뜀. 올린 장 수."""
    c = client()
    if not c or not pics:
        return 0
    have = conn.execute(
        "select count(*) from core.item_photos where case_id = %s", (case_id,)
    ).fetchone()
    if have and have[0]:
        return 0
    seen: set[str] = set()
    n = 0
    for name, b64 in pics:
        if name in seen or n >= MAX:
            continue
        seen.add(name)
        try:
            data, w, h = shrink(b64)
            path = f"{safe_name(case_id)}/{n + 1}.jpg"
            r = c.post(f"/object/{BUCKET}/{path}", content=data,
                       headers={"Content-Type": "image/jpeg", "x-upsert": "true", "Cache-Control": "max-age=604800"})  # fmt: skip
            r.raise_for_status()
        except Exception:  # noqa: BLE001 — 사진 하나가 깨져도 나머지는 계속
            log.warning("사진 올리기 실패 %s %s", case_id, name, exc_info=True)
            continue
        n += 1
        conn.execute(
            """insert into core.item_photos (case_id, seq, path, width, height, bytes) values (%s,%s,%s,%s,%s,%s)
               on conflict (case_id, seq) do update set path = excluded.path, width = excluded.width,
                 height = excluded.height, bytes = excluded.bytes""",
            (case_id, n, path, w, h, len(data)),
        )
    return n


def remove(conn: psycopg.Connection, case_ids: list[str]) -> int:
    """끝난 사건 사진 지우기(Storage + 표)."""
    if not case_ids:
        return 0
    rows = conn.execute(
        "select path from core.item_photos where case_id = any(%s)", (case_ids,)
    ).fetchall()
    paths = [r[0] for r in rows]
    c = client()
    if c and paths:
        for i in range(0, len(paths), 500):
            c.request(
                "DELETE", f"/object/{BUCKET}", json={"prefixes": paths[i : i + 500]}
            ).raise_for_status()
    conn.execute("delete from core.item_photos where case_id = any(%s)", (case_ids,))
    return len(paths)
