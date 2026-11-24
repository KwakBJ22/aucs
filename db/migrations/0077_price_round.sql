-- 「지금 최저가가 감정가에서 몇 번 내린 값인가」(price_round) — 11/24 대표님 「작업해」(서울동부 2024타경57221).
-- 법원 유찰 횟수(yuchalCnt)는 매각조건이 바뀌어 감정가부터 다시 시작해도 계속 쌓임
-- (예: 11번 유찰 · 8.6% → HUG 대항력 포기 확약서 → 감정가 100%로 다시 → 1회 유찰 80% 인데 법원 숫자는 12·13).
-- 이 숫자로 비슷한 물건을 고르면 「12번 유찰된 물건」과 견줘 엉뚱한 예상이 나옴.
-- 11/24 셈: 진행 물건 21,654건 중 928건이 최저가로 센 횟수 < 법원 숫자(그중 922건은 저감률과 딱 맞음).
-- 판단(비교 사례 · 추천 · 찾기 조건 · 유찰 비율)은 price_round, 화면의 「법원 유찰 N회」는 failed_count 그대로.
-- 셈: 최저가 ≥ 감정가 → 0. 아니면 ln(최저가÷감정가) ÷ ln(1 − 법원 저감률) 이 정수(±0.15)이고 법원 숫자보다 작을 때만
-- 그 값, 그 밖(저감률 없는 법원 · 정수 아님 · 법원 숫자가 같거나 작음)은 법원 숫자 그대로.
-- 값은 저장할 때마다 트리거가 넣음(수집기 코드는 그대로) · 아래에서 지난 줄도 채움.

create or replace function core.price_round(p_court text, p_app bigint, p_min bigint, p_failed int)
returns int language sql stable as $$
  select case
    when p_app is null or p_min is null or p_app <= 0 or p_min <= 0 then p_failed
    when p_min >= p_app then 0
    else coalesce((
      select round(x.s)::int
      from (
        select ln(p_min::numeric / p_app) / ln(1 - (t.value -> p_court ->> 'pct')::numeric / 100) as s
        from (select value from ref.rule_tables
              where rule_key = 'court_reduction_pct' and valid_from <= current_date
              order by valid_from desc limit 1) t
        where (t.value -> p_court ->> 'pct') is not null
      ) x
      where abs(x.s - round(x.s)) < 0.15 and (p_failed is null or round(x.s) < p_failed)
    ), p_failed)
  end
$$;

create or replace function core.set_price_round_item() returns trigger language plpgsql as $$
begin
  new.price_round := core.price_round(split_part(new.item_id, '-', 1), new.appraisal_krw, new.min_price_krw, new.failed_count);
  return new;
end $$;

create or replace function core.set_price_round_result() returns trigger language plpgsql as $$
begin
  new.price_round := core.price_round(new.court_code, new.appraisal_krw, new.min_price_krw, new.failed_count);
  return new;
end $$;

alter table core.items add column if not exists price_round integer;
alter table core.rounds add column if not exists price_round integer;
alter table core.sale_results add column if not exists price_round integer;

drop trigger if exists items_price_round on core.items;
create trigger items_price_round before insert or update of appraisal_krw, min_price_krw, failed_count, price_round
  on core.items for each row execute function core.set_price_round_item();
drop trigger if exists rounds_price_round on core.rounds;
create trigger rounds_price_round before insert or update of appraisal_krw, min_price_krw, failed_count, price_round
  on core.rounds for each row execute function core.set_price_round_item();
drop trigger if exists sale_results_price_round on core.sale_results;
create trigger sale_results_price_round before insert or update of appraisal_krw, min_price_krw, failed_count, price_round
  on core.sale_results for each row execute function core.set_price_round_result();

set local statement_timeout = '600s';

-- 지난 줄 채우기(트리거가 값을 셈 — updated_at 은 건드리지 않음)
update core.items set price_round = null;
update core.rounds set price_round = null;
update core.sale_results set price_round = null;

