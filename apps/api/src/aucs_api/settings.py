"""저장소 맨 위 .env 에서 설정을 읽습니다."""

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[4]
load_dotenv(ROOT / ".env")

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
# 화면 주소(CORS). 서비스 주소 + 개발용. Vercel 은 WEB_ORIGINS_EXTRA(쉼표로)에 더 넣을 수 있음(11/3)
WEB_ORIGINS = [
    "https://aucs.co.kr",
    "https://www.aucs.co.kr",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
] + [o.strip() for o in os.getenv("WEB_ORIGINS_EXTRA", "").split(",") if o.strip()]
# 같은 와이파이의 휴대폰에서 개발 화면 보기(192.168.x.x·10.x.x.x:3000) + Vercel 시험 주소(aucs-web-….vercel.app)
WEB_ORIGIN_REGEX = (
    r"http://(192\.168|10)\.\d+\.\d+(\.\d+)?:3000|https://aucs-web(-[a-z0-9-]+)?\.vercel\.app"
)
# Vercel 에서 도는지(그림 등기부 글자 인식은 PC 에서만 — tesseract 가 없음)
ON_VERCEL = bool(os.getenv("VERCEL"))
# Vercel 예약 실행(Cron)이 보내는 비밀값 — /cron/* 주소만 씀
CRON_SECRET = os.getenv("CRON_SECRET", "").strip()

# 관리자 화면 열쇠 (2단계 로그인 전까지 개발용). 비어 있으면 관리자 주소는 모두 막힘.
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "").strip()

# Supabase 로그인 확인용 (공개 키)
SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
SUPABASE_PUBLISHABLE_KEY = os.getenv("SUPABASE_PUBLISHABLE_KEY", "").strip()
# 회원 탈퇴(11/1)에만 씀 — 로그인 계정 지우기는 비밀 키가 있어야 함
SUPABASE_SECRET_KEY = os.getenv("SUPABASE_SECRET_KEY", "").strip().strip("\"'")
# 웹 푸시 (VAPID) 공개 키 — 비밀 키는 수집기(workers)만 씀
VAPID_PUBLIC_KEY = os.getenv("VAPID_PUBLIC_KEY", "").strip()
