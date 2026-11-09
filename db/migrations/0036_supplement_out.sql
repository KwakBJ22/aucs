-- 0036 (11/9 대표님): 지지옥션에서 온 매각결과(origin = 'supplement')를 손님용 표에서 내부용 표로 옮김.
-- 손님 화면(찾기 「매각됨·취하·변경」)과 낙찰가율 계산에 지지옥션 자료가 섞여 있었음. 지우지 않고 옮겨 둠.
create table if not exists ops.supplement_sale_results (like core.sale_results including defaults);
alter table ops.supplement_sale_results enable row level security;  -- 정책 없음 = 손님 쪽에서 못 읽음
revoke all on ops.supplement_sale_results from anon, authenticated;

insert into ops.supplement_sale_results
select * from core.sale_results where origin = 'supplement';

-- 11/8 지지옥션 자료에서만 나와 유찰 기록에 넣었던 회차(2,678건)를 뺌 — 법원 출처가 없는 것만
delete from core.rounds r
where r.fetched_at = '2026-11-08 19:00+09'
  and not exists (select 1 from core.sale_results s
                  where s.item_id = r.item_id and s.sale_date = r.sale_date
                    and s.result = 'failed' and s.origin <> 'supplement');

delete from core.sale_results where origin = 'supplement';
