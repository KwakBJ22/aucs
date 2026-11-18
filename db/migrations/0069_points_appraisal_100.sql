-- 0069 (11/19 대표님): 감정평가서 올리기를 손님 화면에 다시 — 100P · 한 사람 하루 10건까지
-- (11/18 저녁 감정평가서 받는 자동 도구로 법원이 IP 를 막음 → 손님도 많이 받으면 막힐 수 있어 하루 10건으로 막음)
-- 새 줄(valid_from 오늘) — 옛 줄은 그대로 남음(화면 셈은 valid_from <= 오늘 중 가장 늦은 줄).
insert into ref.rule_tables (rule_key, valid_from, value, basis)
select 'points', date '2026-11-19',
       jsonb_set(jsonb_set(value, '{appraisal}', '100'::jsonb), '{daily_max,appraisal}', '10'::jsonb),
       '11/19 대표님: 감정평가서 300P → 100P · 감정평가서는 한 사람 하루 10건까지(넘으면 올리기 자체를 막음 — 법원 차단 예방). '
       || '등기부 1,000P · 하루 제한 없음(999) 등 나머지는 2026-11-01 줄과 같음.'
from ref.rule_tables where rule_key = 'points' and valid_from = date '2026-11-01'
on conflict do nothing;
