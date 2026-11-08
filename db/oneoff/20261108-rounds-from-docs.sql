-- 11/8 유찰 기록 채우기: 이미 받아 둔 법원 문서(기일내역·물건상세 기일 목록)에서 지난 유찰 회차를 core.rounds 로.
-- 예전엔 우리가 목록을 처음 받은 뒤의 회차만 쌓여, 9번 유찰된 물건에 유찰 1번만 있었음(수원 2024타경101239).
-- 표시: fetched_at = '2026-11-08 18:00+09' (되돌리기: delete from core.rounds where fetched_at = '2026-11-08 18:00+09')
-- 앞으로는 문서를 받을 때 수집기가 같은 일을 함(extract/case_docs.py past_failed_rounds).
with latest as (
  select distinct on (case_id, doc_kind) case_id, doc_kind, payload
  from raw.court_doc_raw where doc_kind = 'schedule' or doc_kind like 'item\_detail\_%'
  order by case_id, doc_kind, fetched_at desc),
f as (
  select l.case_id || '-' || split_part(l.doc_kind, '_', 3) as item_id,
         to_date(r->>'dxdyYmd', 'YYYYMMDD') as d,
         nullif(regexp_replace(r->>'tsLwsDspslPrc', '[^0-9]', '', 'g'), '')::bigint as p,
         r->>'dxdyPlcNm' as place
  from latest l, jsonb_array_elements(l.payload->'dma_result'->'gdsDspslDxdyLst') r
  where l.doc_kind like 'item\_detail\_%' and r->>'auctnDxdyKndCd' = '01' and r->>'auctnDxdyRsltCd' = '002'
    and length(r->>'dxdyYmd') = 8
  union all
  select l.case_id || '-' || coalesce(nullif(r->>'dspslGdsSeq', ''), '1'),
         to_date(left(r->>'dxdyTime', 10), 'YYYY.MM.DD'),
         nullif(regexp_replace(r->>'tsLwsDspslPrc', '[^0-9]', '', 'g'), '')::bigint, r->>'dxdyPlcNm'
  from latest l, jsonb_array_elements(l.payload->'dlt_dxdyDtsLst') r
  where l.doc_kind = 'schedule' and r->>'auctnDxdyKndNm' = '매각기일' and r->>'dxdyRslt' = '유찰'),
u as (select distinct on (item_id, d) item_id, d, p, place from f where d is not null
      order by item_id, d, p desc nulls last),
n as (select u.*, row_number() over (partition by u.item_id order by u.d) - 1 as before from u)
insert into core.rounds (round_id, item_id, sale_date, appraisal_krw, min_price_krw, failed_count,
  sale_place, result, fetched_at, checked_at)
select n.item_id || '-' || to_char(n.d, 'YYYYMMDD'), n.item_id, n.d, i.appraisal_krw, n.p, n.before,
  n.place, 'failed', '2026-11-08 18:00+09', now()
from n join core.items i on i.item_id = n.item_id
on conflict (round_id) do update set result = 'failed',
  min_price_krw = coalesce(core.rounds.min_price_krw, excluded.min_price_krw), checked_at = now()
where core.rounds.result <> 'failed';
