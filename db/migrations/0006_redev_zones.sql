-- 0006 서울 정비사업 구역·사업장 (정보몽땅)
create table ref.redev_zones (
  zone_id bigint generated always as identity primary key,
  source text not null,              -- 사업장 목록 / 구역 추진현황
  gu text,                           -- 자치구
  name text not null,
  biz_type text,                     -- 재건축·재개발·가로주택 …
  stage text,                        -- 진행 단계
  address text,                      -- 대표지번 원문
  dong_name text,
  main_no int,
  sub_no int not null default 0,
  op_status text,                    -- 운영 구분 (일시중단 등)
  recent_stage_date date,
  source_date date,
  fetched_at timestamptz not null default now()
);
create index on ref.redev_zones (gu, dong_name, main_no);
comment on table ref.redev_zones is '서울 정비사업 구역·사업장 (정보몽땅). 경매 물건과 같은 동·지번으로 잇기';
revoke all on ref.redev_zones from anon, authenticated;
