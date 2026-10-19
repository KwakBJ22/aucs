"""PC 전문가 보기 (전체 물건 표)."""

from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from aucs_api.services import pro

router = APIRouter(prefix="/pro")


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
def get_case(case_id: str) -> dict[str, Any]:
    d = pro.case_detail(case_id, date.today())
    if d is None:
        raise HTTPException(status_code=404, detail="없는 사건")
    return d
