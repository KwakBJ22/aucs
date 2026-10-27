"""로그인 사용자 확인: 웹이 보낸 Supabase 토큰에서 사용자 id를 얻습니다.

10/27 속도 개선: Supabase 토큰은 ES256 서명이라 공개 키(JWKS)로 이 서버에서 바로 확인합니다
(예전엔 처음 보는 토큰마다 Supabase에 물어 0.3~1.5초 걸렸고, 화면이 동시에 4개를 부르면 4번 물었음).
공개 키는 1시간 기억하고, 모르는 키 번호가 오면 한 번 다시 받습니다.
로컬 확인이 안 되는 토큰(옛 HS256 등)만 예전처럼 Supabase에 묻습니다. 토큰·이메일은 기록하지 않습니다.
"""

import base64
import hashlib
import json
import threading
import time
from typing import Any

import httpx
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature
from fastapi import Header, HTTPException

from aucs_api import settings

REMEMBER = 300.0
KEYS_TTL = 3600.0
LEEWAY = 30  # 시계 차이 허용(초)
_client = httpx.Client(timeout=5)  # 연결을 이어 두고 다시 씀
_known: dict[str, tuple[str, float]] = {}  # 토큰 지문 → (사용자 id, 기억 끝 시각)
_keys: dict[str, ec.EllipticCurvePublicKey] = {}
_keys_at = 0.0
_lock = threading.Lock()


def _b64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _exp(token: str) -> float | None:
    try:
        return float(json.loads(_b64(token.split(".")[1]))["exp"])
    except (IndexError, ValueError, KeyError, TypeError):
        return None


def _load_keys(force: bool = False) -> None:
    global _keys_at
    with _lock:
        if not force and _keys and time.time() - _keys_at < KEYS_TTL:
            return
        try:
            r = _client.get(f"{settings.SUPABASE_URL}/auth/v1/.well-known/jwks.json")
            r.raise_for_status()
            found: dict[str, ec.EllipticCurvePublicKey] = {}
            for k in r.json().get("keys", []):
                if k.get("kty") == "EC" and k.get("crv") == "P-256" and k.get("kid"):
                    nums = ec.EllipticCurvePublicNumbers(
                        int.from_bytes(_b64(k["x"]), "big"),
                        int.from_bytes(_b64(k["y"]), "big"),
                        ec.SECP256R1(),
                    )
                    found[k["kid"]] = nums.public_key()
            _keys.clear()
            _keys.update(found)
        except (httpx.HTTPError, ValueError, KeyError):
            pass  # 못 받으면 아래에서 Supabase에 직접 묻는 방식으로
        _keys_at = time.time()


def verify_local(token: str, now: float) -> str | None:
    """서명·만료·발급처를 직접 확인. 사용자 id(sub) 또는 None(로컬로는 판단 못 함).

    서명이 틀렸거나 만료면 401."""
    try:
        h64, p64, s64 = token.split(".")
        head: dict[str, Any] = json.loads(_b64(h64))
        claims: dict[str, Any] = json.loads(_b64(p64))
        sig = _b64(s64)
    except ValueError:
        raise HTTPException(status_code=401, detail="로그인이 필요해요") from None
    if head.get("alg") != "ES256" or not head.get("kid"):
        return None
    _load_keys()
    key = _keys.get(head["kid"])
    if key is None:
        _load_keys(
            force=time.time() - _keys_at > 60
        )  # 새 키로 바뀌었을 수 있음(너무 자주는 안 받음)
        key = _keys.get(head["kid"])
    if key is None or len(sig) != 64:
        return None
    der = encode_dss_signature(int.from_bytes(sig[:32], "big"), int.from_bytes(sig[32:], "big"))
    try:
        key.verify(der, f"{h64}.{p64}".encode(), ec.ECDSA(hashes.SHA256()))
    except InvalidSignature:
        raise HTTPException(status_code=401, detail="로그인이 필요해요") from None
    if float(claims.get("exp", 0)) + LEEWAY < now:
        raise HTTPException(status_code=401, detail="로그인이 필요해요")
    iss_ok = claims.get("iss") == f"{settings.SUPABASE_URL}/auth/v1"
    if not iss_ok or claims.get("role") != "authenticated":
        raise HTTPException(status_code=401, detail="로그인이 필요해요")
    sub = claims.get("sub")
    return str(sub) if sub else None


def _ask_supabase(token: str) -> str:
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
    uid = r.json().get("id") if r.status_code == 200 else None
    if not uid:
        raise HTTPException(status_code=401, detail="로그인이 필요해요")
    return str(uid)


def current_user_id(authorization: str = Header(default="")) -> str:
    token = authorization.removeprefix("Bearer ").strip()
    if not token or not settings.SUPABASE_URL:
        raise HTTPException(status_code=401, detail="로그인이 필요해요")
    key = hashlib.sha256(token.encode()).hexdigest()
    now = time.time()
    hit = _known.get(key)
    if hit and hit[1] > now:
        return hit[0]
    uid = verify_local(token, now) or _ask_supabase(token)
    until = min(now + REMEMBER, _exp(token) or now + REMEMBER)
    if len(_known) > 5000:
        _known.clear()
    _known[key] = (uid, until)
    return uid
