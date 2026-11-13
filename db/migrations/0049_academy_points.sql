-- 0049 경매 아카데미(11/14 대표님): 한 단계를 다 들으면 포인트. 단계마다 한 번만.
-- 포인트 내역의 이유에 'academy' 를 더하고, 같은 회원 · 같은 단계에는 한 줄만 들어가게 함. 점수는 기준표 points.academy_stage.
alter table app.point_ledger drop constraint if exists point_ledger_reason_check;
alter table app.point_ledger add constraint point_ledger_reason_check
  check (reason = any (array['registry', 'appraisal', 'spend', 'refund', 'admin', 'academy']));
create unique index if not exists point_ledger_academy_once
  on app.point_ledger (user_id, item_id) where reason = 'academy';
update ref.rule_tables set value = value || '{"academy_stage": 100}'::jsonb
 where rule_key = 'points' and not (value ? 'academy_stage');
