-- 0056 (11/15 대표님): 지지옥션 자료를 운영 DB 에서 모두 지움 — 「지지옥션 자료는 우리 시스템에 직접 절대 넣지 않는다」.
-- 무엇이 있었는지는 프로젝트 문서 「공식출처.md」 1절에 적어 둠. 되돌릴 수 없음(원본 낙찰가DB 도 같은 날 지움).
--
-- 1) ops.supplement_sale_results — 11/9(0036)에 손님 표에서 옮겨 둔 지지옥션 입찰당일결과 11,699줄
-- 2) core.sale_results 의 origin = 'court_db' 17,347줄 — 강사 낙찰가DB 「경매낙찰_통합」(지지옥션 + 법원 결합)의 법원 쪽 줄.
--    3분의 2쯤이 지지옥션에도 있던 줄이라 값이 어느 쪽에서 온 것인지 가릴 수 없어 전부 지움.
-- 3) core.rounds 중 그 court_db 줄에서만 나온 유찰 기록(11/8 19:00 에 넣은 것 가운데 법원 수집분이 받쳐 주지 않는 4,978줄)
-- 남는 것: origin = 'court_collect'(우리가 법원에서 받은 것)만.

delete from core.rounds r
where r.fetched_at = '2026-11-08 19:00+09'
  and not exists (select 1 from core.sale_results s
                  where s.item_id = r.item_id and s.sale_date = r.sale_date and s.origin = 'court_collect');

delete from core.sale_results where origin <> 'court_collect';

drop table if exists ops.supplement_sale_results;

comment on column core.sale_results.origin is '내부용 출처: court_collect(우리가 법원에서 받은 것)만 — 11/15 지지옥션 · 강사 낙찰가DB 줄을 모두 지움';
