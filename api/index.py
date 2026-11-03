"""Vercel 에서 옥스 API 를 띄우는 입구(11/3). Vercel 이 이 파일의 `app` 을 부릅니다.

저장소는 uv 작업 공간(apps/api · packages/rules · workers)이라 설치 대신 소스 폴더를 경로에 더함.
밖 패키지는 맨 위 requirements.txt (API 가 쓰는 것만 — 수집기용 Chrome·글자 인식은 PC 에만).
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in ("apps/api/src", "packages/rules/src", "workers/src"):
    sys.path.insert(0, str(ROOT / p))

from aucs_api.main import app  # noqa: E402

__all__ = ["app"]
