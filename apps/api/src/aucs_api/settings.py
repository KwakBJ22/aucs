"""저장소 맨 위 .env 에서 설정을 읽습니다."""

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[4]
load_dotenv(ROOT / ".env")

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
WEB_ORIGINS = ["http://localhost:3000", "http://127.0.0.1:3000"]

# 관리자 화면 열쇠 (2단계 로그인 전까지 개발용). 비어 있으면 관리자 주소는 모두 막힘.
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "").strip()

# Supabase 로그인 확인용 (공개 키)
SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
SUPABASE_PUBLISHABLE_KEY = os.getenv("SUPABASE_PUBLISHABLE_KEY", "").strip()
# 웹 푸시 (VAPID) 공개 키 — 비밀 키는 수집기(workers)만 씀
VAPID_PUBLIC_KEY = os.getenv("VAPID_PUBLIC_KEY", "").strip()
