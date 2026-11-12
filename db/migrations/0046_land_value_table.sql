-- 0046 땅값 역산 추정 시세 기준표(LAND-01, 11/12 대표님 「상하단 넣어」)
-- 건물 원가: ㎡당 새로 짓는 값 × 연면적 × 남은 가치(1 − 지난 해 ÷ 내용연수, 바닥 20%).
-- ㎡당 180만 원은 철근콘크리트 다가구 기준 임시값 — 한국부동산원 건물신축단가표로 맞춰 「검토 끝」 눌러 주세요(관리자 설정 · 기준표).
insert into ref.rule_tables (rule_key, valid_from, value, basis) values
('land_value', '2026-11-01',
 '{"building_per_m2": 1800000, "life_years": 50, "min_residual": 0.2, "months": 24, "min_n": 5}'::jsonb,
 '11/12: 감정평가실무 원가법(재조달원가 × 잔가율) · ㎡당 단가는 한국부동산원 건물신축단가표 확인 전 임시값 · 같은 동 단독·다가구 실거래 24개월 · 5건 이상')
on conflict do nothing;
