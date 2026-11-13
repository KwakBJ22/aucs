-- 0048 필지별 토지이용계획(11/14 대표님 「정비구역 안」) — 브이월드 getLandUseAttr 에서 받은 지역 · 지구 목록.
-- 감정평가서가 아직 없는 물건도 정비구역 · 재정비촉진지구 안인지 가르려는 것. 공개 자료라 API(관리자 연결)만 읽음.
create table if not exists core.parcel_land_use (
  pnu        text primary key,             -- 필지 번호 19자리(법정동 10 + 대지 1/산 2 + 본번 4 + 부번 4)
  uses       jsonb not null,               -- [{"name": "정비구역", "code": "UDT100", "incl": "포함", "since": "2025-05-23"}]
  fetched_at timestamptz not null default now()
);
comment on table core.parcel_land_use is '필지별 토지이용계획(브이월드). land_use 수집기가 진행 물건의 필지만 넣음(11/14).';
alter table core.parcel_land_use enable row level security;
