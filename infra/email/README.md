# 옥스 메일 양식 (Supabase Authentication → Emails → Templates)

| 양식 | 제목 | 파일 |
|---|---|---|
| Confirm signup | 옥스 가입을 마무리해 주세요 | confirm_signup.html |
| Magic Link | 옥스 로그인 링크예요 | magic_link.html |

- `{{ .ConfirmationURL }}` 는 Supabase가 채움. 고치면 이 폴더 파일도 같이 고칠 것.
- 보내는 사람: 옥스 <help@aucs.co.kr> (Resend SMTP, Authentication → Emails → SMTP Settings)
- 돌아올 주소: Site URL http://localhost:3000, Redirect URLs http://localhost:3000/**, http://192.168.219.110:3000/** (서버 옮기면 https://aucs.co.kr/** 로)
