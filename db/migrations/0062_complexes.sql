-- 0062 (11/16): 공동주택 단지 식별정보(한국부동산원, 공공데이터포털 15106817 — api.odcloud.kr AptIdInfoSvc/v1).
-- collectors/complexes.py 가 전국 자료를 받아 수도권(서울 · 경기 · 인천)만 통째로 갈아 끼움 — 분기(redev 와 같이).
-- 필지번호(PNU)로 물건에 이음 → 단지 이름 · 세대수 · 동수 · 사용승인일 · 동마다 지상 층수.

create table if not exists ref.complexes (
  complex_pk text primary key,
  pnu text,                          -- 필지번호 19자리(법정동 10 + 산 1 + 본번 4 + 부번 4)
  address text,
  road_address text,
  names text[] not null default '{}',-- COMPLEX_NM1~3(앞이 대표 이름)
  gb_cd text,                        -- 단지 구분 코드(원문)
  dong_cnt int,
  unit_cnt int,
  use_approved date,                 -- 사용승인일
  dongs jsonb not null default '[]', -- [{"name": "101동", "floors": 15}, …]
  max_floors int,
  fetched_at timestamptz not null default now()
);
create index if not exists complexes_pnu on ref.complexes (pnu);
comment on table ref.complexes is '공동주택 단지 식별정보(한국부동산원) — 수도권, 분기 갱신';
revoke all on ref.complexes from anon, authenticated;
