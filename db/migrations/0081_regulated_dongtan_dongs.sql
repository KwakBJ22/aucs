-- 11/25 입찰가 계산 점검: 규제지역 「화성시 동탄구」(2026.7.1 지정)를 주소 글자로만 찾았는데, 법원 주소에는 새 구 이름이
--   없음(「경기도 화성시 오산동 1023 …」) → 동탄 물건이 수도권 비규제(대출 70%)로 셈됐음(진행 주택 14건 등).
--   동탄구 법정동으로도 찾도록 같은 표의 새 줄(11/25부터).
insert into ref.rule_tables (rule_key, valid_from, value, basis)
select 'regulated_areas', date '2026-11-25',
       value || jsonb_build_object('gyeonggi_dongs', jsonb_build_object('화성시', jsonb_build_array(
         '석우동','반송동','능동','영천동','오산동','청계동','신동','중동','목동','산척동','방교동','장지동','금곡동','송동','여울동'))),
       basis || ' · 11/25: 동탄구는 법원 주소에 구 이름이 없어 법정동(석우 · 반송 · 능 · 영천 · 오산 · 청계 · 신 · 중 · 목 · 산척 · 방교 · 장지 · 금곡 · 송 · 여울동)으로도 찾음'
from ref.rule_tables where rule_key = 'regulated_areas' and valid_from = date '2026-07-01'
on conflict do nothing;
