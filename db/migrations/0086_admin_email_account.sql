-- 관리자 전용 계정(11/27 대표님): 관리자 OTP 를 할 때 Supabase 가 같은 계정의 다른 로그인을 지워
-- 휴대폰(카카오 계정)이 자꾸 로그아웃됐음 → 관리자는 이메일 계정 futuregram7@gmail.com 으로 따로.
-- 카카오 계정(kbjkwak@gmail.com)의 관리자 권한은 새 계정 OTP 등록 뒤 대표님 확인 받고 뺌(여기선 그대로).
insert into app.admins (user_id, role)
select id, 'owner' from auth.users where email = 'futuregram7@gmail.com'
on conflict (user_id) do nothing;
