"""로그인 사용자 확인: 웹이 보낸 Supabase 토큰을 Supabase에 물어 사용자 id를 얻습니다.

카카오·이메일 어느 쪽으로 로그인해도 같은 방식입니다. 토큰·이메일은 기록하지 않습니다.
"""

import httpx
from fastapi import Header, HTTPException

from aucs_api import settings


def current_user_id(authorization: str = Header(default="")) -> str:
    token = authorization.removeprefix("Bearer ").strip()
    if not token or not settings.SUPABASE_URL:
        raise HTTPException(status_code=401, detail="로그인이 필요해요")
    try:
        r = httpx.get(
            f"{settings.SUPABASE_URL}/auth/v1/user",
            headers={
                "apikey": settings.SUPABASE_PUBLISHABLE_KEY,
                "Authorization": f"Bearer {token}",
            },
            timeout=5,
        )
    except httpx.HTTPError as e:
        raise HTTPException(status_code=503, detail="로그인 확인 실패") from e
    if r.status_code != 200:
        raise HTTPException(status_code=401, detail="로그인이 필요해요")
    uid = r.json().get("id")
    if not uid:
        raise HTTPException(status_code=401, detail="로그인이 필요해요")
    return str(uid)
