-- 이름이 바뀐 법정동: 법원·온비드 주소가 옛 이름으로 와도 새 동 코드로 붙게.
-- 예) 화성 오산동 → 동탄구 여울동(2026-03-01, 4159711500). 전엔 좌표로 옆 동(청계·영천)에 붙었음.
create table if not exists ref.dong_alias (
  sido text not null,
  city text not null,          -- 주소 두 번째 낱말(시·군·구)
  old_name text not null,
  new_name text not null,
  changed_on date,
  primary key (sido, city, old_name)
);
insert into ref.dong_alias values ('경기도', '화성시', '오산동', '여울동', '2026-03-01')
on conflict do nothing;

CREATE OR REPLACE FUNCTION ref.region_code_for(p_court text, p_address text, p_lon double precision DEFAULT NULL::double precision, p_lat double precision DEFAULT NULL::double precision)
 RETURNS text
 LANGUAGE plpgsql
 STABLE
AS $function$
declare
  v_addr text := btrim(coalesce(p_address, ''));
  v_sido text := split_part(btrim(coalesce(p_address, '')), ' ', 1);
  v_city text := split_part(btrim(coalesce(p_address, '')), ' ', 2);
  v_pt geography := case when p_lon is null or p_lat is null then null
                         else st_setsrid(st_makepoint(p_lon, p_lat), 4326)::geography end;
  v_dong text;
  v_new text;
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
  v_dong := substring(v_addr from '\(([가-힣][가-힣0-9]*(?:동|가|읍|면))[,)[:space:]]');
  if v_dong is null then
    v_dong := substring(v_addr from '[[:space:]]([가-힣][가-힣0-9]*(?:동|가|읍|면))(?:[[:space:]]|$)');
  end if;

  if v_dong is not null then
    select a.new_name into v_new from ref.dong_alias a
     where a.sido = v_sido and a.city = v_city and a.old_name = v_dong;
    if v_new is not null then
      select array_agg(region_code), count(*) into v_cands, v_n
        from ref.regions r
       where r.level = 'dong' and r.sido = v_sido and r.eupmyeondong = v_new
         and split_part(r.sigungu, ' ', 1) = v_city;
      if v_n = 1 then
        return v_cands[1];
      end if;
    end if;
    select array_agg(region_code), count(*) into v_cands, v_n
      from ref.regions r
     where r.level = 'dong' and r.sido = v_sido and r.eupmyeondong = v_dong
       and v_addr like r.sido || ' ' || r.sigungu || ' %';
    if v_n <> 1 then
      select array_agg(region_code), count(*) into v_cands, v_n
        from ref.regions r
       where r.level = 'dong' and r.sido = v_sido and r.eupmyeondong = v_dong
         and position(' ' in r.sigungu) > 0
         and v_addr like r.sido || ' ' || split_part(r.sigungu, ' ', 1) || ' %';
    end if;
    if v_n = 1 then
      v_code := v_cands[1];
    elsif v_n > 1 and v_pt is not null then
      select c into v_code
        from unnest(v_cands) c
       order by (select min(i.geom <-> v_pt) from core.items i where i.region_code = c and i.geom is not null) nulls last
       limit 1;
    end if;
  end if;

  if v_code is null and v_pt is not null then
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
  if p_court ~ '^[0-9]{10}$' and left(p_court, 8) = left(v_code, 8) then
    return p_court;
  end if;
  return v_code;
end;
$function$;
