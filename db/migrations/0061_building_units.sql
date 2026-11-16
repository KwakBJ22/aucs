-- 0061 (11/16): 건축물대장 전유공용면적 — 물건마다 그 「호」 줄만(건축HUB getBrExposPubuseAreaInfo, 지번 + hoNm).
-- collectors/units.py 가 아침 묶음에서 하루 1,200건씩 받음. 물건 한 건 = 한 줄(같은 지번이라도 호가 다르므로 물건 단위).
-- 분석이 전유 용도(근생빌라 판단 보강) · 전유/공용 면적(전용률)을 읽음.

create table if not exists core.building_units (
  item_id text primary key,
  region_code text not null,
  lot_no text not null,
  ho_name text,                      -- 맞은 호 이름(「416」 · 「416호」 · 「B102」 …), 못 찾으면 null
  result text not null check (result in ('ok', 'none')),
  own_area numeric,                  -- 전유 면적 합(㎡)
  common_area numeric,               -- 공용 면적 합(㎡)
  own_use text,                      -- 전유 주용도(「다세대주택」 · 「제2종근린생활시설」 …)
  own_use_etc text,                  -- 전유 기타용도(대장 원문)
  rows jsonb not null default '[]',  -- 받은 줄 그대로(그 호의 전유 · 공용)
  fetched_at timestamptz not null default now()
);
create index if not exists building_units_lot on core.building_units (region_code, lot_no);
comment on table core.building_units is '건축물대장 전유공용면적 — 물건의 호 줄만(분석이 읽음)';
revoke all on core.building_units from anon, authenticated;
