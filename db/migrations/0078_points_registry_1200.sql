-- 11/24 대표님: 등기부 새로 떼서 올리면 1,200P(열람 수수료가 1,100원으로 올라 100P 더)
--   등기부 · 감정평가서 모두 포인트는 한 사람 하루 10건까지 — 더 올리는 것은 받되 포인트 없음(감정평가서 올리기 막음은 풂)
--   나머지 값은 2026-11-19 줄과 같음. 화면은 valid_from <= 오늘 중 가장 늦은 줄을 씀.
insert into ref.rule_tables (rule_key, valid_from, value, basis)
select 'points', date '2026-11-24',
       value || jsonb_build_object('registry', 1200, 'appraisal', 100,
                                   'daily_max', jsonb_build_object('registry', 10, 'appraisal', 10)),
       '11/24 대표님: 등기부 1,000P → 1,200P(열람 수수료 1,100원 + 100P) · 등기부 · 감정평가서 모두 포인트는 하루 10건까지, 더 올려도 받되 포인트 없음(감정평가서 올리기 막음 풂). 나머지는 2026-11-19 줄과 같음.'
from ref.rule_tables
where rule_key = 'points' and valid_from = date '2026-11-19'
  and not exists (select 1 from ref.rule_tables where rule_key = 'points' and valid_from = date '2026-11-24');

select valid_from, value -> 'registry' as registry, value -> 'daily_max' as daily_max
from ref.rule_tables where rule_key = 'points' order by valid_from;
