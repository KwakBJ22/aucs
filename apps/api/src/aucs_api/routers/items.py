"""물건 목록·지역 (공개)."""

from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query

from aucs_api.services import item_detail, items

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


@router.get("/items/{item_id}")
def get_item(item_id: str) -> dict[str, Any]:
    d = item_detail.detail(item_id, date.today())
    if d is None:
        raise HTTPException(404, "물건을 찾을 수 없어요")
    return d
