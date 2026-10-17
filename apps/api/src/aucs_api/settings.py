"""저장소 맨 위 .env 에서 설정을 읽습니다."""

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[4]
load_dotenv(ROOT / ".env")

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
WEB_ORIGINS = ["http://localhost:3000", "http://127.0.0.1:3000"]
