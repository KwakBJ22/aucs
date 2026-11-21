-- 법원 관심등록 수(11/21 대표님 「작업해」 — 경매레이더에 있던 것): 법원 경매정보 사이트에서 이 물건을
-- 관심 물건으로 담은 사람 수(법원 응답 gwansMulRegCnt). 수집기가 버리고 있었음 → 물건에 저장.
-- 지난 값은 법원에 다시 묻지 않고 이미 받아 둔 원문(raw.court_item_raw, 10/17~)에서 채움.
-- 11/21 셈(10/20~ 아파트, 1회 유찰): 관심 0~2명 낙찰 24% · 3~5명 39% · 6명+ 65% — 경쟁 신호로 씀.
alter table core.items add column if not exists court_interest integer;
alter table core.items add column if not exists court_interest_at date;  -- 그 값을 받은 날(한국 시각)

set local statement_timeout = '300s';

with r as (
  select distinct on (item_id) item_id, cnt, at
  from (
    select (payload->>'boCd') || '-' || (payload->>'srnSaNo') || '-'
             || coalesce(nullif(payload->>'maemulSer', '')::int, 1) as item_id,
           nullif(payload->>'gwansMulRegCnt', '')::int as cnt,
           (fetched_at at time zone 'Asia/Seoul')::date as at,
           fetched_at
    from raw.court_item_raw
  ) x
  order by item_id, fetched_at desc
)
update core.items i
set court_interest = r.cnt, court_interest_at = r.at
from r
where r.item_id = i.item_id
  and i.court_interest_at is null;
