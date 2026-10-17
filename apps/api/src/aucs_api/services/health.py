"""연결 확인. 접속 문자열·비밀번호는 어떤 경우에도 돌려주지 않습니다."""

from typing import Any

import psycopg

from aucs_api import settings


def check_db() -> dict[str, Any]:
    """DB에 붙어 PostGIS 버전을 읽어 봅니다."""
    if not settings.DATABASE_URL:
        return {"ok": False, "reason": "DATABASE_URL 이 비어 있음"}
    try:
        with psycopg.connect(settings.DATABASE_URL, connect_timeout=5) as conn:
            row = conn.execute("select postgis_version()").fetchone()
        return {"ok": True, "postgis": row[0] if row else None}
    except Exception as e:  # noqa: BLE001 — 사유 종류만 알림
        return {"ok": False, "reason": type(e).__name__}
