-- 0041 감정평가서 포인트 500 → 300(11/12 대표님 — 법원에서 무료로 받는 서류라)
update ref.rule_tables set value = jsonb_set(value, '{appraisal}', '300'::jsonb),
       basis = replace(basis, '감정평가서는 법원 무료 500P', '감정평가서는 법원 무료 300P(11/12 500 → 300)')
where rule_key = 'points' and valid_from = '2026-11-01';
