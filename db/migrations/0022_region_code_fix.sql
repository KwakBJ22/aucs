-- 0022 지역 코드 바로잡기 (10/27, MCP로 적용함)
-- 법원이 주는 행정구역 코드(srchHjguRdCd)에 옛 코드가 섞여 있음
--   금천구 11540→11545 · 강북구 11300→11305 · 광진구 11210→11215 · 파주 41510→41480
--   고양 덕양구 41471→41281 · 이천 41530→41500 · 부천 41195→41192 · 화성 41590→2026 새 구(41591~41597)
--   수원 권선·장안·팔달은 동 번호만 다름(연무동 4111111400→4111113700)
-- 그래서 건축물대장이 구 단위로 통째 비고(100% 빈 결과), 실거래 시세 맞추기도 빠졌음.
-- 규칙: 법원 코드가 법정동 표(ref.regions dong)에 있으면 그대로. 없으면 주소의 동·가·읍·면 이름과
--       「시도 시군구」로 표에서 하나로 정해질 때만 바꿈. 법원 코드가 같은 읍·면 아래 리(里) 코드면
--       그대로 둠(표엔 리가 없고 리 코드가 더 정확함 — 건축물대장 받음 490 · 빈 결과 21).
-- 원래 법원 코드는 region_code_court 에 남김. 적용 때 물건 2,505건·매각결과 1,095건 바뀜.

create or replace function ref.region_code_for(p_court text, p_address text)
returns text
language plpgsql
stable
as $$
declare
  v_addr text := btrim(coalesce(p_address, ''));
  v_sido text := split_part(btrim(coalesce(p_address, '')), ' ', 1);
  v_dong text;
  v_code text;
  v_n int;
begin
  if p_court is not null and exists (
    select 1 from ref.regions where region_code = p_court and level = 'dong'
  ) then
    return p_court;
  end if;
  if v_addr = '' then
    return p_court;
  end if;
  -- 도로명 주소는 괄호 안 첫 이름이 법정동: "… (연무동,로잔빌)", 지번 주소는 시군구 다음 낱말
  v_dong := substring(v_addr from '\(([가-힣][가-힣0-9]*(?:동|가|읍|면))[,)[:space:]]');
  if v_dong is null then
    v_dong := substring(v_addr from '[[:space:]]([가-힣][가-힣0-9]*(?:동|가|읍|면))(?:[[:space:]]|$)');
  end if;
  if v_dong is null then
    return p_court;
  end if;
  select min(region_code), count(*) into v_code, v_n
    from ref.regions r
   where r.level = 'dong' and r.sido = v_sido and r.eupmyeondong = v_dong
     and v_addr like r.sido || ' ' || r.sigungu || ' %';
  if v_n <> 1 then
    -- 구가 새로 생긴 시(화성 등): 주소엔 「화성시 기산동」, 표엔 「화성시 병점구 기산동」
    select min(region_code), count(*) into v_code, v_n
      from ref.regions r
     where r.level = 'dong' and r.sido = v_sido and r.eupmyeondong = v_dong
       and position(' ' in r.sigungu) > 0
       and v_addr like r.sido || ' ' || split_part(r.sigungu, ' ', 1) || ' %';
  end if;
  if v_n <> 1 then
    return p_court;
  end if;
  if p_court ~ '^[0-9]{10}$' and left(p_court, 8) = left(v_code, 8) then
    return p_court;
  end if;
  return v_code;
end;
$$;

comment on function ref.region_code_for(text, text) is
  '법원 지역 코드가 법정동 표에 없으면 주소의 동 이름으로 바로잡음 (0022)';

alter table core.items add column if not exists region_code_court text;
alter table core.sale_results add column if not exists region_code_court text;

-- 한 번만: 기존 자료 바로잡기
update core.items set region_code_court = region_code where region_code_court is null;
update core.items i set region_code = x.new, updated_at = now()
  from (select item_id, ref.region_code_for(region_code_court, address) new from core.items) x
 where x.item_id = i.item_id and i.region_code is distinct from x.new;
update core.sale_results set region_code_court = region_code
 where region_code_court is null and region_code is not null;
update core.sale_results s set region_code = ref.region_code_for(s.region_code_court, s.address)
 where s.region_code_court is not null
   and s.region_code is distinct from ref.region_code_for(s.region_code_court, s.address);
