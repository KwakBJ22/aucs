-- 0079 11/24 대표님: 포인트는 1번 결제에 결제금액의 80%까지(이전 50%).
--   유효기간은 그대로 — 무료 기간 포인트는 유료 전환일부터 1년, 전환 뒤 포인트는 받은 날부터 1년(expire_days 365).
--   2026-11-24 줄(0078)의 pay_max_pct 만 바꿈.
update ref.rule_tables
set value = value || '{"pay_max_pct": 80}'::jsonb,
    basis = basis || ' · 11/24: 결제 금액의 50% → 80%까지'
where rule_key = 'points' and valid_from = date '2026-11-24'
  and (value ->> 'pay_max_pct')::int is distinct from 80;

select valid_from, value -> 'pay_max_pct' as pay_max_pct from ref.rule_tables where rule_key = 'points' order by valid_from;
