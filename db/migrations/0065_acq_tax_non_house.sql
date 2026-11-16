-- 0065 (11/16): 취득세 기준표에 주택 아닌 것의 세율 — 상가 · 오피스텔 · 땅에 주택 세율(중과 8.4% 등)이 붙던 것을 바로잡음.
-- 지방세법 §11①7: 농지 외 4% · 농지 3%. 지방교육세 0.4% / 0.2%, 농어촌특별세 0.2% → 4.6% / 3.4%.
update ref.rule_tables
set value = value || '{"non_house": {"other": {"rate": 4, "edu": 0.4, "farm": 0.2}, "farm": {"rate": 3, "edu": 0.2, "farm": 0.2}}}'::jsonb,
    basis = basis || ' · 주택 외 §11①7(농지 외 4% · 농지 3%, 교육세 · 농특세 포함 4.6% · 3.4%)'
where rule_key = 'acquisition_tax' and not (value ? 'non_house');
