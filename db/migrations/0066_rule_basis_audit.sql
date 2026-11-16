-- 0066 (11/17): 기준표 근거 점검 — 공식 출처와 대조해 틀린 글 · 낡은 값을 바로잡음.
-- 숫자 대조 결과(11/17): 소액임차 · 상가 환산보증금 · 취득세(기본 · 중과 · 교육세 · 농특세 · 주택 외) · 재산세 · 종부세 · LTV · 규제지역 목록 · 스트레스 금리 — 값 일치.
-- 바꾸는 것: 생애최초 근거 글(추징 요건 개정 반영), 취득세 근거 글(생애최초 감면은 따로 반영 중), DSR 심사 금리 가정(4.5 → 4.88 실제 평균),
--           종부세 근거 글(2026 세제개편안 미반영 표시), 규제지역 근거 글(공고 번호 확인 안 됨), LTV 옛 줄 끝 날짜.

update ref.rule_tables
set basis = '지방세특례제한법 §36의3 생애최초 주택 구입 취득세 감면: 12억 이하 유상취득, 200만 원 한도(소득 요건 없음), 2028.12.31 취득분까지. '
         || '추징: 2025.12.31 개정 후 납세의무 성립분은 3년 안에 매각 · 증여 · 임대 등 다른 용도로 쓸 때만(3개월 상시거주 · 추가 취득 요건 삭제 — 금천구청 안내로 확인). '
         || '300만 원 한도 유형(소형 · 저가 주택, 인구감소지역)은 이 표에 없음 — 조건이 출처마다 달라 확인 전이라 200만 원으로만 셈(감면을 덜 잡는 쪽). '
         || '2026 지방세제 개편안(40세 미만 300만 · 주거용 오피스텔 포함)은 국회 통과 확인 전이라 반영 안 함. [법률 검토 전 — 11/17 출처 대조]'
where rule_key = 'first_home_relief' and valid_from = '2025-01-01';

update ref.rule_tables
set basis = replace(basis, '일시적 2주택·생애최초 감면은 반영 안 함.', '일시적 2주택은 반영 안 함(생애최초 감면은 first_home_relief 표로 뺌).')
         || ' · 11/17 대조: 중과 교육세 0.4%, 85㎡ 초과 농특세 0.2 / 0.6 / 1.0% 일치'
where rule_key = 'acquisition_tax' and valid_from = '2020-08-12';

update ref.rule_tables
set value = jsonb_set(value, '{base_rate_pct}', '4.88'::jsonb),
    basis = '은행권 차주 DSR 40%, 스트레스 DSR 3단계(수도권 · 규제지역 주담대 가산 3.0%p, 지방 0.75%p 유예 중), 만기 30년, 원리금균등. '
         || '심사 금리 4.88% = 한국은행 2026년 9월 예금은행 신규취급액 주담대 가중평균(11/17 확인, 10월분 발표 전). 기준금리 3.00%(2026.8.27 인상, 10.22 동결). '
         || '실제 금리는 은행 · 고정/변동 · 신용에 따라 다름 — 매달 바뀌는 값. [검토 전 — 개발 기준]'
where rule_key = 'dsr' and valid_from = '2026-08-01';

update ref.rule_tables
set basis = basis || ' · 11/17 대조: 2026년 귀속분 세율 · 공제 · 60% 일치. 2026 세제개편안(2027년부터 비율 70%, 거주 1주택 공제 14억 등)은 국회 통과 확인 전이라 반영 안 함'
where rule_key = 'comprehensive_tax_home' and valid_from = '2026-01-01';

update ref.rule_tables
set basis = basis || ' · 11/17 대조: 2026년도분 1세대1주택 43 · 44 · 45%(시행령 §109) 일치'
where rule_key = 'property_tax_home' and valid_from = '2026-01-01';

update ref.rule_tables
set basis = replace(basis, '+ 국토교통부공고 제2026-882호(2026.7.1, 화성 동탄구·용인 기흥구·구리시)',
                    '+ 국토교통부 2026.6.30 추가 지정(7.1 효력, 화성 동탄구·용인 기흥구·구리시 — 보도로 확인, 공고 번호는 확인 안 됨)')
where rule_key = 'regulated_areas' and valid_from = '2026-07-01';

update ref.rule_tables
set valid_to = '2026-10-17',
    basis = replace(basis, ' DSR·스트레스 금리는 반영 안 함.', '')
where rule_key = 'loan_ltv' and valid_from = '2026-07-01' and valid_to is null;

update ref.rule_tables
set basis = basis || ' · 11/17 대조: 규제지역 40% · 생애최초 70% · 비규제 70%(지방 생애최초 80%, 지방 다주택 60%) · 가격별 한도 일치(정책브리핑). 규제지역 서민 · 실수요자 60%는 표에 없음'
where rule_key = 'loan_ltv' and valid_from = '2026-10-18';
