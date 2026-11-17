"""PC 전문가 보기 (전체 물건 표) — 로그인 · 이용권이 있어야 봄(11/17, CSV 내려받기 포함)."""

from datetime import date, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import Response

from aucs_api.auth.user import current_user_id
from aucs_api.services import access, pro


def pro_viewer(authorization: str = Header(default="")) -> str:
    uid = current_user_id(authorization)
    access.allowed(uid, None)
    return uid


router = APIRouter(prefix="/pro", dependencies=[Depends(pro_viewer)])


@router.get("/items", response_model=None)
def get_pro_items(
    sido: Annotated[str | None, Query(max_length=20)] = None,
    sigungu: Annotated[list[str] | None, Query()] = None,
    court: Annotated[list[str] | None, Query()] = None,
    usage: Annotated[list[str] | None, Query()] = None,
    exclude: Annotated[list[str] | None, Query()] = None,
    failed_min: Annotated[int | None, Query(ge=0)] = None,
    failed_max: Annotated[int | None, Query(ge=0)] = None,
    app_min: Annotated[int | None, Query(ge=0)] = None,
    app_max: Annotated[int | None, Query(ge=0)] = None,
    price_max: Annotated[int | None, Query(ge=0)] = None,
    rate_max: Annotated[int | None, Query(ge=1, le=100)] = None,
    days_max: Annotated[int | None, Query(ge=0, le=60)] = None,
    q: Annotated[str | None, Query(max_length=40)] = None,
    source: Annotated[str, Query(pattern="^(all|court|onbid)$")] = "all",
    sort: Annotated[str, Query(pattern="^(deadline|rate|appraisal|price|failed)$")] = "deadline",
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    fmt: Annotated[str, Query(pattern="^(json|csv)$")] = "json",
) -> dict[str, Any] | Response:
    f = {k: v for k, v in locals().items() if k not in ("sort", "page", "limit", "fmt")}
    if fmt == "csv":
        out = pro.search(f, date.today(), sort=sort, page=1, limit=5000)
        return Response(
            pro.to_csv(out["rows"]),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": "attachment; filename=aucs_items.csv"},
        )
    return pro.search(f, date.today(), sort=sort, page=page, limit=limit)


@router.get("/cases")
def get_cases(
    category: Annotated[str | None, Query(max_length=30)] = None,
    q: Annotated[str | None, Query(max_length=40)] = None,
) -> dict[str, Any]:
    return {
        "categories": [*pro.WATCH_CATS, "종기 뒤 신고"],
        "cases": pro.cases(category, q, date.today()),
    }


@router.get("/cases/{case_id}")
def get_case(case_id: str, authorization: str = Header(default="")) -> dict[str, Any]:
    access.count_view(current_user_id(authorization), case_id)
    d = pro.case_detail(case_id, date.today())
    if d is None:
        raise HTTPException(status_code=404, detail="없는 사건")
    return d


@router.get("/market")
def get_market(
    sido: Annotated[str | None, Query(max_length=20)] = None,
    sigungu: Annotated[str | None, Query(max_length=20)] = None,
    court: Annotated[str | None, Query(max_length=10)] = None,
    usage: Annotated[list[str] | None, Query()] = None,
    months: Annotated[int, Query(ge=1, le=12)] = 3,
    source: Annotated[str, Query(pattern="^(court|onbid)$")] = "court",
) -> dict[str, Any]:
    today = date.today()
    f = {"sido": sido, "sigungu": sigungu, "court": court, "usage": usage,
         "since": today - timedelta(days=months * 31)}  # fmt: skip
    if source == "onbid":
        return pro.onbid_market(f)
    return pro.market(f, today)
