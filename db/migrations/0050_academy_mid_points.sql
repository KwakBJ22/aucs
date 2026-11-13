-- 0050 경매 아카데미 중급 포인트(11/14): 중급은 수업마다 옥스에서 해 보는 과제가 있어 한 단계 200.
update ref.rule_tables set value = value || '{"academy_stage_mid": 200}'::jsonb
 where rule_key = 'points' and not (value ? 'academy_stage_mid');
