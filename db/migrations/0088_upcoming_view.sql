-- 예정물건 2단계(11/27 대표님 「작업해」 — 손님 화면 「곧 나올 물건」 미리보기 · 관심 담기).
-- ① 목록 구분(auctnLstDvsCd): 01 토지 · 02 건물 · 03 집합건물 · 04 자동차 · 06 선박 · 12 중기 · 99 기타.
--    자동차 · 중기 · 선박은 주소 칸에 사람 주소가 들어와 칸이 밀렸음 → 화면 · 알림은 01 · 02 · 03 만.
-- ② 지역 코드: 물건과 같은 함수(ref.region_code_for)로 — 같은 단지 실거래를 붙이는 열쇠(region_code + lot_no).
-- ③ 관심 담기: 공고 전 사건을 담아 두면 매각공고(물건 목록)에 들어올 때 알림 + 관심 물건으로 옮김(jobs/notify.py).

alter table core.upcoming_cases add column if not exists list_kind text;
alter table core.upcoming_cases add column if not exists region_code text;

update core.upcoming_cases u
   set list_kind = r.payload->>'auctnLstDvsCd'
  from (select distinct on (court_code, payload->>'userCsNo') court_code, payload->>'userCsNo' case_no, payload
          from raw.court_notice_raw order by court_code, payload->>'userCsNo', fetched_at desc) r
 where r.court_code = u.court_code and r.case_no = u.case_no and u.list_kind is null;

update core.upcoming_cases
   set region_code = ref.region_code_for(null, concat_ws(' ', sido, sigungu, split_part(dong, ' ', 1)))
 where region_code is null and list_kind in ('01', '02', '03');

create index if not exists upcoming_cases_lot on core.upcoming_cases (region_code, lot_no);

create table if not exists app.upcoming_watches (
  user_id      uuid not null references auth.users (id) on delete cascade,
  court_code   text not null,
  case_no      text not null,
  created_at   timestamptz not null default now(),
  notified_at  timestamptz,                -- 매각공고에 들어와 알림을 보낸 때
  primary key (user_id, court_code, case_no)
);
create index if not exists upcoming_watches_case on app.upcoming_watches (court_code, case_no);
comment on table app.upcoming_watches is '공고 전 사건 관심 — 매각공고되면 알림 · 관심 물건으로 옮김. 11/27';
alter table app.upcoming_watches enable row level security;
