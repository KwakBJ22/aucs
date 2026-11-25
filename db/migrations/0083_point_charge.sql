-- 0083 포인트 충전(11/26 대표님): 회원이 포인트함에서 직접 충전.
-- 충전 주문은 pay_orders(plan='points')에만 남기고 이용권 표(payments)에는 넣지 않음
-- (payments 는 「이용권이 있나」를 보는 곳이 여럿이라 섞이면 충전만 해도 이용권이 열림).
-- 충전한 포인트는 point_ledger(reason='charge')에 한 줄.
alter table app.pay_orders drop constraint if exists pay_orders_plan_check;
alter table app.pay_orders add constraint pay_orders_plan_check
  check (plan = any (array['personal','pro','one','points']));

alter table app.point_ledger drop constraint if exists point_ledger_reason_check;
alter table app.point_ledger add constraint point_ledger_reason_check
  check (reason = any (array['registry','appraisal','spend','refund','admin','academy','charge']));
