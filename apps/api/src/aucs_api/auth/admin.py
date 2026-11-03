"""관리자 확인(11/2): 옥스 로그인 + 관리자 표(app.admins) + 2단계 인증(aal2).

역할: owner(대표) > operator(운영자) > viewer(보기). 바꾸는 주소는 require_role 로 막습니다.
ADMIN_TOKEN 은 서버 사이 작업(스케줄러)만 씀 — 화면에서는 쓰지 않습니다. 토큰·이메일은 기록하지 않습니다.
"""

import base64
import json
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, HTTPException

from aucs_api import settings
from aucs_api.auth.user import current_user_id
from aucs_api.db import connect

RANK = {"viewer": 1, "operator": 2, "owner": 3}


@dataclass
class Admin:
    user_id: str | None  # 서버 열쇠로 들어오면 None
    role: str
    mfa: bool


def _aal(token: str) -> str:
    try:
        p = token.split(".")[1]
        return str(json.loads(base64.urlsafe_b64decode(p + "=" * (-len(p) % 4))).get("aal", ""))
    except (IndexError, ValueError):
        return ""


def admin_login(
    authorization: str = Header(default=""), x_admin_token: str = Header(default="")
) -> Admin:
    """로그인한 관리자인지(2단계 인증 전이어도 통과 — /admin/me 에서만 씀)."""
    if (
        x_admin_token
        and settings.ADMIN_TOKEN
        and secrets.compare_digest(x_admin_token, settings.ADMIN_TOKEN)
    ):
        return Admin(None, "owner", True)
    uid = current_user_id(authorization)  # 서명·만료 확인
    with connect() as c:
        row = c.execute("select role from app.admins where user_id = %s", (uid,)).fetchone()
    if not row:
        raise HTTPException(status_code=403, detail="관리자 권한이 없습니다")
    return Admin(uid, row["role"], _aal(authorization.removeprefix("Bearer ").strip()) == "aal2")


def require_admin(a: Annotated[Admin, Depends(admin_login)]) -> Admin:
    if not a.mfa:
        raise HTTPException(status_code=403, detail="mfa")
    return a


def require_role(role: str) -> Callable[..., Admin]:
    def dep(a: Annotated[Admin, Depends(require_admin)]) -> Admin:
        if RANK[a.role] < RANK[role]:
            raise HTTPException(status_code=403, detail="이 일은 권한이 없어요")
        return a

    return dep
