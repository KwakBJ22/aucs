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
    q: Annotated[str | None, Query(max_length=40)] = None,
    status: Annotated[str, Query(pattern="^(active|sold|withdrawn|all)$")] = "active",
) -> dict[str, Any]:
    """진행 중 물건(items)과 끝난 사건(results). status 에 따라 한쪽 또는 둘 다."""
    out: dict[str, Any] = {"total": 0, "items": [], "results": [], "exact_item_id": None}
    if status in ("active", "all"):
        out.update(items.list_items(
            sigungu=sigungu or [], max_cash=max_cash, sort=sort, limit=limit, today=date.today(), q=q,
        ))  # fmt: skip
    if status != "active":
        out.update(items.search_results(q=q, status=status, sigungu=sigungu or [], limit=limit))
    return out


@router.get("/regions")
def get_regions() -> list[dict[str, Any]]:
    return items.regions()


@router.get("/items/{item_id}")
def get_item(item_id: str) -> dict[str, Any]:
    d = item_detail.detail(item_id, date.today())
    if d is None:
        raise HTTPException(404, "물건을 찾을 수 없어요")
    return d


@router.get("/items/{item_id}/bid-check")
def get_bid_check(item_id: str, bid: Annotated[int, Query(ge=1)]) -> dict[str, Any]:
    d = item_detail.bid_check(item_id, bid)
    if d is None:
        raise HTTPException(404, "물건을 찾을 수 없어요")
    return d


@router.get("/items/{item_id}/calc")
def get_calc(
    item_id: str,
    bid: Annotated[int | None, Query(ge=1)] = None,
    homes: Annotated[int, Query(ge=0, le=5)] = 0,
    first: bool = False,
    loan: Annotated[int | None, Query(ge=0)] = None,
    selling: bool = False,
    income: Annotated[int | None, Query(ge=0)] = None,
    other_monthly: Annotated[int, Query(ge=0)] = 0,
) -> dict[str, Any]:
    d = item_detail.calc(
        item_id, bid_krw=bid, homes=homes, first_time=first, loan_krw=loan,
        selling=selling, income_krw=income, other_monthly_krw=other_monthly,
    )  # fmt: skip
    if d is None:
        raise HTTPException(404, "물건을 찾을 수 없어요")
    return d
