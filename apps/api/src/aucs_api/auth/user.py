"""로그인 사용자 확인: 웹이 보낸 Supabase 토큰을 Supabase에 물어 사용자 id를 얻습니다.

카카오·이메일 어느 쪽으로 로그인해도 같은 방식입니다. 토큰·이메일은 기록하지 않습니다.
같은 토큰은 한 번 확인하면 잠시(최대 5분, 토큰 만료 전까지) 기억해 다시 묻지 않습니다(10/20 속도 개선).
"""

import base64
import hashlib
import json
import time

import httpx
from fastapi import Header, HTTPException

from aucs_api import settings

REMEMBER = 300.0
_client = httpx.Client(timeout=5)  # 연결을 이어 두고 다시 씀
_known: dict[str, tuple[str, float]] = {}  # 토큰 지문 → (사용자 id, 기억 끝 시각)


def _exp(token: str) -> float | None:
    """토큰에 적힌 만료 시각(검증은 Supabase가 이미 함 — 여기서는 기억 기간만 정함)."""
    try:
        part = token.split(".")[1]
        data = json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))
        return float(data["exp"])
    except (IndexError, ValueError, KeyError, TypeError):
        return None


def current_user_id(authorization: str = Header(default="")) -> str:
    token = authorization.removeprefix("Bearer ").strip()
    if not token or not settings.SUPABASE_URL:
        raise HTTPException(status_code=401, detail="로그인이 필요해요")
    key = hashlib.sha256(token.encode()).hexdigest()
    now = time.time()
    hit = _known.get(key)
    if hit and hit[1] > now:
        return hit[0]
    try:
        r = _client.get(
            f"{settings.SUPABASE_URL}/auth/v1/user",
            headers={
                "apikey": settings.SUPABASE_PUBLISHABLE_KEY,
                "Authorization": f"Bearer {token}",
            },
        )
    except httpx.HTTPError as e:
        raise HTTPException(status_code=503, detail="로그인 확인 실패") from e
    if r.status_code != 200:
        raise HTTPException(status_code=401, detail="로그인이 필요해요")
    uid = r.json().get("id")
    if not uid:
        raise HTTPException(status_code=401, detail="로그인이 필요해요")
    until = min(now + REMEMBER, _exp(token) or now + REMEMBER)
    if len(_known) > 5000:
        _known.clear()
    _known[key] = (str(uid), until)
    return str(uid)
