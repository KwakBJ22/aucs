-- 0084 잘못된 정보 알리기 1,000P(11/26 대표님): 「이 값이 틀렸어요」 제보(app.value_reports, 0018)를 관리자가 「고침」으로 닫으면
--   같은 물건 · 같은 칸(section)에서 처음 고친 제보 한 사람에게 1,000P. 하루 상한 없음.
insert into ref.rule_tables (rule_key, valid_from, value, basis)
select 'points', date '2026-11-26', value || '{"report": 1000}'::jsonb,
       basis || ' · 11/26 대표님: 잘못된 정보 알리기 1,000P(관리자가 고친 것만 · 하루 상한 없음 · 같은 물건 같은 칸은 처음 한 사람)'
from (select value, basis from ref.rule_tables where rule_key = 'points' order by valid_from desc limit 1) p
on conflict (rule_key, valid_from) do update set value = ref.rule_tables.value || '{"report": 1000}'::jsonb;

-- 0083(charge)까지 넣은 이유에 report 를 더함
alter table app.point_ledger drop constraint if exists point_ledger_reason_check;
alter table app.point_ledger add constraint point_ledger_reason_check
  check (reason = any (array['registry','appraisal','spend','refund','admin','academy','charge','report']));

alter table app.value_reports add column if not exists points int not null default 0;
