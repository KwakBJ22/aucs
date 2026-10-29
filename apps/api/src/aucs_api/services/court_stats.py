"""법원별 응찰자 수: 회원이 남긴 입찰 결과(app.bid_results.bidder_count)로 쌓음. 법원 사이트엔 응찰자 수가 없어 회원 기록이 유일한 자료."""

from statistics import median
from typing import Any

from aucs_api.db import connect

MIN_N = 5  # 이보다 적으면 평균을 말하지 않음

_SQL = """
select b.bidder_count
from app.bid_results b join core.items i using (item_id) join core.cases c using (case_id)
where c.court_code = (select c2.court_code from core.items i2 join core.cases c2 using (case_id) where i2.item_id = %s)
  and b.bidder_count is not null and b.bidder_count > 0 and b.sale_date > current_date - 365
"""


def summarize(counts: list[int]) -> dict[str, Any]:
    """(순수 함수) 5건 미만이면 건수만."""
    n = len(counts)
    if n < MIN_N:
        return {"n": n, "avg": None, "median": None, "min_n": MIN_N}
    return {"n": n, "avg": round(sum(counts) / n, 1), "median": median(counts), "min_n": MIN_N}


def court_bidders(item_id: str) -> dict[str, Any] | None:
    if item_id.startswith("OB-"):
        return None
    with connect() as c:
        rows = c.execute(_SQL, (item_id,)).fetchall()
    return summarize([int(r["bidder_count"]) for r in rows])
