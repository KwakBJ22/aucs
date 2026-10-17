"""물건 목록·지역 (공개)."""

from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Query

from aucs_api.services import items

router = APIRouter()


@router.get("/items")
def get_items(
    sigungu: Annotated[list[str] | None, Query()] = None,
    max_cash: Annotated[int | None, Query(ge=0)] = None,
    sort: Annotated[str, Query(pattern="^(deadline|rate)$")] = "deadline",
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
) -> dict[str, Any]:
    return items.list_items(
        sigungu=sigungu or [], max_cash=max_cash, sort=sort, limit=limit, today=date.today()
    )


@router.get("/regions")
def get_regions() -> list[dict[str, Any]]:
    return items.regions()
