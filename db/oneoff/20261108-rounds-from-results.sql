-- 11/8 유찰 기록 채우기 2: 매일 받아 온 매각 결과(core.sale_results, 7월~)의 「유찰」을 core.rounds 로.
-- 표시: fetched_at = '2026-11-08 19:00+09' (되돌리기: delete from core.rounds where fetched_at = '2026-11-08 19:00+09')
with s as (
  select distinct on (s.item_id, s.sale_date) s.item_id, s.sale_date, s.min_price_krw
  from core.sale_results s join core.items i on i.item_id = s.item_id
  where s.result = 'failed'
  order by s.item_id, s.sale_date, s.min_price_krw desc nulls last)
insert into core.rounds (round_id, item_id, sale_date, appraisal_krw, min_price_krw, failed_count,
  result, fetched_at, checked_at)
select s.item_id || '-' || to_char(s.sale_date, 'YYYYMMDD'), s.item_id, s.sale_date, i.appraisal_krw,
  s.min_price_krw, null, 'failed', '2026-11-08 19:00+09', now()
from s join core.items i on i.item_id = s.item_id
on conflict (round_id) do update set result = 'failed', checked_at = now(),
  min_price_krw = coalesce(core.rounds.min_price_krw, excluded.min_price_krw)
where core.rounds.result <> 'failed';

-- 그 회차 전 유찰 횟수: 지금 유찰 횟수에서 최근 회차부터 하나씩 뺌(넣은 물건만, 맞지 않는 44건은 비워 둠)
with t as (select distinct item_id from core.rounds where fetched_at = '2026-11-08 19:00+09'),
r as (
  select r.round_id, i.failed_count - row_number() over (partition by r.item_id order by r.sale_date desc) as before
  from core.rounds r join t using (item_id) join core.items i on i.item_id = r.item_id
  where r.result = 'failed' and r.sale_date < i.sale_date)
update core.rounds x set failed_count = r.before
from r where x.round_id = r.round_id and x.failed_count is null and r.before >= 0;
