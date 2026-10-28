-- 0023 지역 코드 바로잡기 2 — 좌표로 가려냄 (10/28)
-- 0022 뒤에도 117건이 옛 코드로 남음:
--   ① 같은 동 이름이 여러 구에 있음(화성 「능동」 = 병점구·동탄구) → 하나로 못 정함
--   ② 도로명만 있고 동 이름이 없는 주소(「금천구 탑골로 54-3」)
-- 물건 좌표(geom)로:
--   ① 후보 동 가운데, 이미 맞는 코드를 가진 물건이 가장 가까이 있는 동 (이미 맞는 물건 868건으로 시험: 99.1%)
--   ② 같은 시도·시군구에서 1km 안 가장 가까운, 맞는 코드를 가진 물건의 동 (1,500건 시험: 동 94.7% · 구 98.7%)
-- ②는 동이 틀려도 건축물대장·시세는 지번까지 맞아야 붙으므로 엉뚱한 자료가 붙을 일은 드묾.
-- 원래 법원 코드는 그대로 region_code_court 에 있음.

drop function if exists ref.region_code_for(text, text);

create or replace function ref.region_code_for(
  p_court text, p_address text, p_lon double precision default null, p_lat double precision default null
)
returns text
language plpgsql
stable
as $$
declare
  v_addr text := btrim(coalesce(p_address, ''));
  v_sido text := split_part(btrim(coalesce(p_address, '')), ' ', 1);
  v_city text := split_part(btrim(coalesce(p_address, '')), ' ', 2);
  v_pt geography := case when p_lon is null or p_lat is null then null
                         else st_setsrid(st_makepoint(p_lon, p_lat), 4326)::geography end;
  v_dong text;
  v_code text;
  v_n int := 0;
  v_cands text[];
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

  if v_dong is not null then
    select array_agg(region_code), count(*) into v_cands, v_n
      from ref.regions r
     where r.level = 'dong' and r.sido = v_sido and r.eupmyeondong = v_dong
       and v_addr like r.sido || ' ' || r.sigungu || ' %';
    if v_n <> 1 then
      -- 구가 새로 생긴 시(화성 등): 주소엔 「화성시 기산동」, 표엔 「화성시 병점구 기산동」
      select array_agg(region_code), count(*) into v_cands, v_n
        from ref.regions r
       where r.level = 'dong' and r.sido = v_sido and r.eupmyeondong = v_dong
         and position(' ' in r.sigungu) > 0
         and v_addr like r.sido || ' ' || split_part(r.sigungu, ' ', 1) || ' %';
    end if;
    if v_n = 1 then
      v_code := v_cands[1];
    elsif v_n > 1 and v_pt is not null then
      -- ① 후보가 여럿: 이미 맞는 코드를 가진 물건이 가장 가까운 후보
      select c into v_code
        from unnest(v_cands) c
       order by (select min(i.geom <-> v_pt) from core.items i where i.region_code = c and i.geom is not null) nulls last
       limit 1;
    end if;
  end if;

  if v_code is null and v_pt is not null then
    -- ② 동 이름이 없거나 못 찾음: 같은 시도·시(군구) 안 1km 안의 가장 가까운, 맞는 코드를 가진 물건
    select i.region_code into v_code
      from core.items i
      join ref.regions r on r.region_code = i.region_code and r.level = 'dong'
     where i.geom is not null and st_dwithin(i.geom, v_pt, 1000)
       and r.sido = v_sido and split_part(r.sigungu, ' ', 1) = v_city
     order by i.geom <-> v_pt
     limit 1;
  end if;

  if v_code is null then
    return p_court;
  end if;
  -- 법원 코드가 같은 읍·면 아래 리(里) 코드면 그쪽이 더 정확함(표엔 리가 없음)
  if p_court ~ '^[0-9]{10}$' and left(p_court, 8) = left(v_code, 8) then
    return p_court;
  end if;
  return v_code;
end;
$$;

comment on function ref.region_code_for(text, text, double precision, double precision) is
  '법원 지역 코드가 법정동 표에 없으면 주소의 동 이름 → 좌표 순으로 바로잡음 (0022·0023)';

-- 한 번만(10/28 MCP로 함): 물건 114건 바로잡음, 남은 3건
-- update core.items i set region_code = x.new, updated_at = now()
--   from (select item_id, ref.region_code_for(region_code_court, address, st_x(geom::geometry), st_y(geom::geometry)) new from core.items) x
--  where x.item_id = i.item_id and i.region_code is distinct from x.new;
