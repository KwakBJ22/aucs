-- 11/9 유찰 횟수 바로잡기: 법원 목록 숫자가 실제보다 적은 물건(대부분 서울중앙, 1회씩 적음).
-- 유찰 기록 수가 더 크고, 최저가 비율(법원 저감률로 거꾸로 센 횟수)과 맞을 때만 기록 수로 바꿈.
-- 앞으로는 수집기(store.fix_failed_count)가 같은 판단을 매일 함. 바꾼 물건은 updated_at 을 올려 아침 분석이 다시 셈.
with red as (
  select key as court, (value ->> 'pct')::numeric as pct
  from jsonb_each((select value from ref.rule_tables where rule_key = 'court_reduction_pct'
                   order by valid_from desc limit 1))),
f as (
  select r.item_id, count(distinct r.sale_date)::int as n
  from core.rounds r join core.items i using (item_id)
  where r.result = 'failed' and r.sale_date < i.sale_date
  group by r.item_id),
fix as (
  select i.item_id, f.n
  from core.items i join f using (item_id)
  join red on red.court = split_part(i.item_id, '-', 1)
  where f.n > coalesce(i.failed_count, 0) and i.min_price_krw > 0 and i.min_price_krw < i.appraisal_krw
    and round(ln(i.min_price_krw::numeric / i.appraisal_krw) / ln(1 - red.pct / 100)) = f.n)
update core.items i set failed_count = fix.n, updated_at = now()
from fix where i.item_id = fix.item_id;

-- 회차별 「그 전 유찰 횟수」 다시 셈(11/8 넣은 기록): 기록이 다 있으면 첫 회차부터 0,1,2…, 아니면 지금 횟수에서 거꾸로
with t as (select distinct item_id from core.rounds where fetched_at in ('2026-11-08 18:00+09', '2026-11-08 19:00+09')),
r as (
  select r.round_id, r.item_id, i.failed_count,
    count(*) over (partition by r.item_id) as n,
    row_number() over (partition by r.item_id order by r.sale_date) - 1 as asc_before,
    i.failed_count - row_number() over (partition by r.item_id order by r.sale_date desc) as desc_before
  from core.rounds r join t using (item_id) join core.items i on i.item_id = r.item_id
  where r.result = 'failed' and r.sale_date < i.sale_date)
update core.rounds x set failed_count = case when r.n >= r.failed_count then r.asc_before else r.desc_before end
from r where x.round_id = r.round_id
  and (case when r.n >= r.failed_count then r.asc_before else r.desc_before end) >= 0
  and x.failed_count is distinct from (case when r.n >= r.failed_count then r.asc_before else r.desc_before end);
