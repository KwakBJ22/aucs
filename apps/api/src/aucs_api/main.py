"""옥스 API 시작점. 실행: uv run uvicorn aucs_api.main:app --port 8100"""

import re
import traceback

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from aucs_api import settings
from aucs_api.cache import PublicCache
from aucs_api.db import warm
from aucs_api.routers import admin, errors, events, health, items, me, pro
from aucs_api.services import errors as error_log

app = FastAPI(title="옥스 API", on_startup=[warm])
app.add_middleware(PublicCache)  # CORS보다 안쪽(먼저 추가)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.WEB_ORIGINS,
    allow_origin_regex=settings.WEB_ORIGIN_REGEX,
    allow_methods=["GET", "PUT", "POST", "PATCH", "DELETE"],  # PATCH: 등기부 「이 줄 고치기」
    allow_headers=["*"],
    max_age=7200,  # 사전 확인(OPTIONS) 응답을 브라우저가 2시간 기억 — 로그인 요청마다 왕복 한 번 줄임
)
app.include_router(health.router)
app.include_router(admin.router)
app.include_router(items.router)
app.include_router(me.router)
app.include_router(pro.router)
app.include_router(events.router)
app.include_router(errors.router)


@app.exception_handler(Exception)
async def on_error(request: Request, exc: Exception) -> JSONResponse:
    """못 잡은 오류: ops.errors 에 남기고(관리자 「오류」) 화면에는 짧은 말만."""
    error_log.save(
        "api", f"{type(exc).__name__}: {exc}", path=f"{request.method} {request.url.path}",
        stack="".join(traceback.format_exception(exc))[-4000:],
    )  # fmt: skip
    # 오류 응답은 CORS 층을 거치지 않아 브라우저가 내용을 못 읽고 화면이 「불러오는 중」에 멈춤(11/1) → 허용 머리글을 직접 붙임
    origin = request.headers.get("origin", "")
    ok = origin in settings.WEB_ORIGINS or bool(re.fullmatch(settings.WEB_ORIGIN_REGEX, origin))
    headers = {"Access-Control-Allow-Origin": origin, "Vary": "Origin"} if ok else None
    return JSONResponse(
        {"detail": "잠시 문제가 생겼어요. 다시 해 주세요"}, status_code=500, headers=headers
    )
