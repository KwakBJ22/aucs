-- 0067 (11/17): 법원별 유찰 저감률을 우리가 법원에서 받은 최저가로 확인해 바꿈.
-- 확인 방법: 최근 60일 안 매각기일 · 한 번 유찰된 물건의 「최저가 ÷ 감정가」(11/17 08:0x 셈). 법원마다 거의 전부가 0.8 또는 0.7.
-- 바로잡음: 안양(B000254) 30% → 20%(80건 중 80건이 0.8). 인천(B000240) 표에 없던 것 → 30%(1,070건 중 1,061건이 0.7).
-- 경기 · 인천의 「확인 전 30%」는 모두 자료로 확인돼 verified true. 지우는 것 없음(같은 줄 값 · 근거 글만 바꿈).
update ref.rule_tables
set value = '{
  "B000210": {"pct": 20, "verified": true, "n": 296, "hit": 279},
  "B000211": {"pct": 20, "verified": true, "n": 156, "hit": 155},
  "B000212": {"pct": 20, "verified": true, "n": 731, "hit": 731},
  "B000213": {"pct": 20, "verified": true, "n": 253, "hit": 250},
  "B000215": {"pct": 20, "verified": true, "n": 97, "hit": 95},
  "B000214": {"pct": 30, "verified": true, "n": 333, "hit": 330},
  "B214807": {"pct": 30, "verified": true, "n": 327, "hit": 324},
  "B214804": {"pct": 30, "verified": true, "n": 184, "hit": 184},
  "B000241": {"pct": 30, "verified": true, "n": 354, "hit": 351},
  "B000250": {"pct": 30, "verified": true, "n": 694, "hit": 688},
  "B000251": {"pct": 30, "verified": true, "n": 250, "hit": 247},
  "B000252": {"pct": 30, "verified": true, "n": 197, "hit": 176},
  "B000253": {"pct": 30, "verified": true, "n": 294, "hit": 291},
  "B250826": {"pct": 30, "verified": true, "n": 290, "hit": 287},
  "B000254": {"pct": 20, "verified": true, "n": 80, "hit": 80},
  "B000240": {"pct": 30, "verified": true, "n": 1070, "hit": 1061}
}'::jsonb,
    basis = '법원별 유찰 저감률 — 11/17 우리가 법원에서 받은 최저가로 확인: 최근 60일 안 매각기일 · 한 번 유찰된 물건의 최저가 ÷ 감정가가 '
         || '0.8(20%) 또는 0.7(30%)인 건수(n 중 hit). 나머지 줄의 까닭은 확인 안 함. '
         || '서울 다섯 곳 · 안양 20%, 그 밖 경기 · 인천 30%. 확인 안 된 법원(verified false 또는 없음)은 화면에 다음 회차 값을 내지 않음.'
where rule_key = 'court_reduction_pct' and valid_to is null;
