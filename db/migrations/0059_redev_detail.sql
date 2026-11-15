-- 0059 (11/15): 정비구역에 단계 날짜 · 세대수를 둘 칸. 서울 열린데이터광장 「서울특별시 도시정비사업 통계」(OA-22856, 분기 갱신)를
-- 우리가 직접 받아 source = '도시정비사업 통계' 줄로 넣음(collectors/redev_seoul.py) — 강사 파일을 뺀 자리를 공식 자료로 채움.
-- detail: {"dates": {"designated", "committee", "union", "review", "plan", "disposal", "move_start", "move_end", "construction"},
--          "homes": {"old", "new", "sale", "rent"}} — 있는 것만.

alter table ref.redev_zones add column if not exists detail jsonb;
comment on column ref.redev_zones.detail is '단계 날짜(dates) · 세대수(homes) — 서울시 도시정비사업 통계에서 받은 줄에만';
comment on column ref.redev_zones.source is '출처: 사업장 목록(서울 정보몽땅) · 도시정비사업 통계(서울 열린데이터광장 OA-22856) — 둘 다 우리가 직접 받는 것';
