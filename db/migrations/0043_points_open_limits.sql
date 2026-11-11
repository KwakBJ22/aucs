-- 0043 포인트(11/12 대표님): 무료 기간에는 하루 제한을 사실상 풀고(각 999건), 결제 한 번에 금액의 50%까지 쓰게 미리 정함.
-- 무료 기간에 받은 포인트는 기한을 정하지 않음(expires_at 비움) — 유료로 바꾸는 날 「그날부터 1년」으로 한꺼번에 정함.
update ref.rule_tables
set value = value || '{"daily_max": {"registry": 999, "appraisal": 999}, "pay_max_pct": 50, "free_period": true}'::jsonb,
    basis = basis || ' · 11/12: 무료 기간 하루 제한 풂(999) · 결제 금액의 50%까지 · 무료 기간 포인트는 전환일부터 1년'
where rule_key = 'points' and valid_from = '2026-11-01';
update app.point_ledger set expires_at = null where delta > 0;
