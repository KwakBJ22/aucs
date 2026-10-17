"""저장소 맨 위 .env 의 DATABASE_URL 로 DB에 붙습니다."""

import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[3]
load_dotenv(ROOT / ".env")


def connect() -> psycopg.Connection:
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError("DATABASE_URL 이 비어 있습니다 (.env)")
    return psycopg.connect(url)
