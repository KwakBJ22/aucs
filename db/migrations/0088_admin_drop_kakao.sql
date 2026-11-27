-- 11/27 대표님: 관리자는 이메일 계정(futuregram7, 0086 · OTP 등록함)만 — 카카오 계정(kbjkwak@gmail.com) 관리자 권한 뺌.
-- 카카오 계정에서 관리자 OTP 를 하면 Supabase 가 그 계정의 다른 로그인(휴대폰)을 지워 자꾸 로그아웃됐음.
delete from app.admins
where user_id = (select id from auth.users where email = 'kbjkwak@gmail.com')
  and exists (select 1 from app.admins a join auth.users u on u.id = a.user_id
              where u.email = 'futuregram7@gmail.com' and a.role = 'owner');
