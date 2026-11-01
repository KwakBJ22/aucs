-- 탈퇴해도 입찰 결과는 통계로 남김(11/1 대표님): 회원 번호만 비움(예전엔 함께 지워졌음)
alter table app.bid_results alter column user_id drop not null;
alter table app.bid_results drop constraint bid_results_user_id_fkey;
alter table app.bid_results add constraint bid_results_user_id_fkey foreign key (user_id) references auth.users(id) on delete set null;
comment on column app.bid_results.user_id is '탈퇴하면 비움(11/1) — 입찰 결과는 법원 응찰자 수 통계로 남김';
