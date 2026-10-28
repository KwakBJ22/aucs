"""물건 목록·지역 (공개)."""

from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query

from aucs_api.services import docs, item_calc, item_detail, items, onbid_detail

router = APIRouter()


@router.get("/items")
def get_items(
    sigungu: Annotated[list[str] | None, Query()] = None,
    max_cash: Annotated[int | None, Query(ge=0)] = None,
    sort: Annotated[str, Query(pattern="^(deadline|rate)$")] = "deadline",
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
    q: Annotated[str | None, Query(max_length=40)] = None,
    status: Annotated[str, Query(pattern="^(active|sold|withdrawn|all)$")] = "active",
    usage: Annotated[list[str] | None, Query()] = None,
    exclude: Annotated[list[str] | None, Query()] = None,
    failed_min: Annotated[int | None, Query(ge=0, le=30)] = None,
    rate_max: Annotated[int | None, Query(ge=1, le=100)] = None,
    days_max: Annotated[int | None, Query(ge=0, le=365)] = None,
    area_min: Annotated[float | None, Query(ge=0)] = None,
    area_max: Annotated[float | None, Query(ge=0)] = None,
    price_max: Annotated[int | None, Query(ge=0)] = None,
    source: Annotated[str, Query(pattern="^(all|court|onbid)$")] = "all",
) -> dict[str, Any]:
    """진행 중 물건(items)과 끝난 사건(results). status 에 따라 한쪽 또는 둘 다."""
    out: dict[str, Any] = {"total": 0, "items": [], "results": [], "exact_item_id": None}
    if status in ("active", "all"):
        out.update(items.list_items(
            sigungu=sigungu or [], max_cash=max_cash, sort=sort, limit=limit, today=date.today(), q=q,
            extra={"usage": usage, "exclude": exclude, "failed_min": failed_min, "rate_max": rate_max,
                   "days_max": days_max, "area_min": area_min, "area_max": area_max, "price_max": price_max},
            source=source,
        ))  # fmt: skip
    if status != "active":
        out.update(items.search_results(q=q, status=status, sigungu=sigungu or [], limit=limit))
    return out


@router.get("/regions")
def get_regions() -> list[dict[str, Any]]:
    return items.regions()


@router.get("/items/{item_id}")
def get_item(item_id: str) -> dict[str, Any]:
    if item_id.startswith("OB-"):  # 공매(온비드) — 10/28
        d = onbid_detail.detail(item_id, date.today())
        if not d:
            raise HTTPException(404, "물건을 찾을 수 없어요")
        return d
    d = item_detail.detail(item_id, date.today())
    if d is None:
        raise HTTPException(404, "물건을 찾을 수 없어요")
    return d


@router.get("/items/{item_id}/docs")
def get_item_docs(item_id: str) -> dict[str, Any]:
    """DOC-01 원문 보기 (현황조사서·문건송달내역)."""
    d = docs.item_docs(item_id)
    if d is None:
        raise HTTPException(404, "물건을 찾지 못했어요")
    return d


@router.get("/items/{item_id}/bid-check")
def get_bid_check(item_id: str, bid: Annotated[int, Query(ge=1)]) -> dict[str, Any]:
    d = item_calc.bid_check(item_id, bid)
    if d is None:
        raise HTTPException(404, "물건을 찾을 수 없어요")
    return d


@router.get("/items/{item_id}/bid-day")
def get_bid_day(item_id: str) -> dict[str, Any]:
    d = item_calc.bid_day(item_id, date.today())
    if d is None:
        raise HTTPException(status_code=404, detail="없는 물건")
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
    d = item_calc.calc(
        item_id, bid_krw=bid, homes=homes, first_time=first, loan_krw=loan,
        selling=selling, income_krw=income, other_monthly_krw=other_monthly,
    )  # fmt: skip
    if d is None:
        raise HTTPException(404, "물건을 찾을 수 없어요")
    # 입찰표 실수 막기 검사도 같이(10/27 — 예전엔 계산·검사를 따로 두 번 불렀음)
    sel = bid or (d.get("selected") or {}).get("bid_krw")
    return {**d, "check": item_calc.bid_check(item_id, sel) if sel else None}
