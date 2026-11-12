-- 0044 이용권 가격을 기준표로(11/12 대표님): 관리자 「이용권·포인트」에서 새 버전을 만들면 적용일부터 바뀜.
-- 이용권 화면(/plans)과 환불 계산(1년권 중간 해지 = 그때 매달 요금)이 같은 값을 읽는다.
insert into ref.rule_tables (rule_key, valid_from, value, basis, reviewed_at) values
('plans', '2026-11-01',
 '{"personal": {"month": 29000, "year": 249000},
   "pro": {"month": 49000, "year": 419000},
   "one": {"one": 9900}}'::jsonb,
 '11/12 대표님: 개인 29,000/1년 249,000 · 전문가 49,000/1년 419,000(지금은 숨김) · 한 건 9,900',
 now())
on conflict do nothing;
