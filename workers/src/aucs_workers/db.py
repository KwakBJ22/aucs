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
    # 연결이 중간에 끊겨도 영원히 기다리지 않게(11/2 분석이 아무 쿼리 없이 50분 멈춤): 30초 조용하면 확인, 3번 답 없으면 끊음
    conn = psycopg.connect(
        url,
        connect_timeout=15,
        keepalives=1,
        keepalives_idle=30,
        keepalives_interval=10,
        keepalives_count=3,
    )
    # 11/18: DB 는 세계 표준시(UTC)라 current_date · ::date 가 한국 0~9시에 「어제」였음 → 이 연결은 한국 시각으로
    conn.execute("set time zone 'Asia/Seoul'")
    conn.commit()
    return conn
