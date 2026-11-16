-- 0064 (11/16): 상가 주변 가게의 자료 기준일 · 토지 실거래를 동마다 빨리 찾는 색인.
-- 기준일은 공공데이터포털 파일 이름(「소상공인시장진흥공단_상가(상권)정보_20260630」)에서 수집기가 읽음.

alter table core.item_stores add column if not exists as_of date;

create index if not exists trades_land_dong on core.trades (left(region_code, 8), deal_date)
  where prop_type = 'land';

-- 11/16 에 받은 500건 — 그날 파일판 이름이 「…_20260630」(공공데이터포털 15083033, 수정일 2026-08-05)
update core.item_stores set as_of = '2026-06-30' where as_of is null and fetched_at < '2026-11-17';
