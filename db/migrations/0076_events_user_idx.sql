-- 0076 (11/23) 관리자 회원 화면: 회원마다 마지막 방문 · 최근 활동을 app.events 에서 읽음 → 회원별 색인
-- 지우는 것 없음 · 여러 번 돌려도 같음
create index if not exists events_user_at on app.events (user_id, at desc) where user_id is not null;
