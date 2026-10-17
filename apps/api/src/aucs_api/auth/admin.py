"""관리자 열쇠 확인 (2단계 카카오 로그인·권한으로 바꿀 자리)."""

import secrets

from fastapi import Header, HTTPException

from aucs_api import settings


def require_admin(x_admin_token: str = Header(default="")) -> None:
    if not settings.ADMIN_TOKEN or not secrets.compare_digest(x_admin_token, settings.ADMIN_TOKEN):
        raise HTTPException(status_code=403, detail="관리자 권한이 없습니다")
