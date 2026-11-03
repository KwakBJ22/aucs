# 옥스(aucs) 작업 지침

부동산 경매 정보 서비스 「옥스」의 저장소입니다. 휴대폰 우선 웹(PWA) + PC 전문가 보기 + 관리자.
기술: Next.js(apps/web) · FastAPI(apps/api) · PostgreSQL/PostGIS(Supabase 서울) · Python 수집기(workers) · 분석 규칙(packages/rules).

## 읽기 순서
1. `docs/design/` 설계 요약(데이터 → 폴더 → 코드 규칙)과 `docs/glossary.md`를 먼저 읽는다.
   화면을 만들거나 고칠 때는 `docs/design/08-look.md`(선 대신 면·여백·큰 버튼)를 먼저 본다.
2. 설계에 없는 화면·표·주소는 만들지 말고 먼저 묻는다.

## 역할 나누기
- **DB 구조·권한(RLS)·자료 옮기기·Supabase 설정은 하지 않는다.** 필요하면 「코워크에 넘길 일」로 보고에 적는다.
  (이주 파일 `db/migrations/*.sql`은 코워크가 쓰고 적용한다. 읽기만 한다.)
- 화면·API 코드·검사 도구·시험·화면 문구는 여기서 한다.

## 하지 않는 것
- 운영 DB·운영서버에 접속하거나 바꾸지 않는다. 내 PC와 개발용 Supabase만.
- 스키마를 이주 파일 없이 바꾸지 않는다. raw 표를 고치거나 지우지 않는다.
- 비밀값을 코드·로그·커밋에 넣지 않는다. 출력하지 않는다. `.env`는 읽기만.
- 원천 사이트(법원 등)에 시험 목적으로 접속하지 않는다(저장된 응답 사용). 로그인이 필요한 수집을 만들지 않는다. 차단 우회 금지.
- 지지옥션 등 외부 서비스 자료·이름을 쓰거나 옮기지 않는다. 감정평가서는 화면에 보이지 않는다.
- 저장소 밖의 폴더(`D:\Auction\system` 등)를 수정하지 않는다. 지금 시스템은 8000 포트를 쓰므로 새 API는 8100, 웹은 3000.

## 이름
- DB 표·열: 영어 snake_case, 표는 복수. 금액 `_krw`(원, bigint), 날짜 `_date`, 시각 `_at`(timestamptz).
- Python: snake_case / 클래스 PascalCase. TypeScript: camelCase / 컴포넌트 PascalCase / 파일 kebab-case.
- 경매 용어의 영어 이름은 `docs/glossary.md`에만 정한다. 새 이름이 필요하면 먼저 사전에 추가.

## 구조
- 규칙(`packages/rules`)은 순수 함수만: DB·네트워크·현재 시각을 직접 쓰지 않음(기준일은 인자).
  결과는 항상 `value`, `status`(확정/추정/확인 필요/모름), `evidence`, `rule_id`를 함께 돌려준다.
- 바뀌는 숫자(세율·LTV·소액임차 금액)는 코드에 쓰지 않고 기준표(`ref.rule_tables`)에서 읽는다.
- API: 라우터는 요청을 받고 서비스를 부르기만. 공개 설정(`display_policy`) 걸러내기는 서비스 한 곳에서.
- 수집기는 원천당 파일 하나, 저장은 raw에만. 요청 간격·하루 한도·이상 응답 시 중단은 공통 모듈로.
- 화면 컴포넌트는 자료를 직접 부르지 않고 `apps/web/lib/api`를 통해서만.
- 화면 모양은 `apps/web/app/styles/` 한 곳에(값은 tokens.css). 화면 파일에 `style={{ }}` 로 고정 값을 쓰지 않고 클래스를 쓴다 — 바뀌는 값만 예외(08-look 8절).
- 화면 문구는 `apps/web/lib/copy.ko.ts` 한 곳에. 쉬운 일상 말, 같은 설명을 칸마다 되풀이하지 않는다. UI는 간략하고 깔끔하게.

## 도구
- Python 3.12 + uv · ruff · mypy(rules는 strict) · pytest
- TypeScript strict + pnpm · eslint + prettier · Vitest · Playwright(휴대폰 375px 먼저)
- GitHub Actions가 올릴 때마다 형식·타입·시험을 돌린다. 커밋 전 gitleaks.
- 시험은 돈·권리 규칙과 대표 흐름에 집중. 불필요한 시험은 만들지 않는다.

## 브랜치·커밋
- 작업은 `feat/<화면ID 또는 기능>` 브랜치 → PR로 `main`.
- 커밋: `feat(rules): 가족 임차인 신호` 처럼 종류(feat/fix/docs/refactor/test/chore) + 범위 + 한글 요약.
- 함수 첫 줄에 한글로 「무엇을 왜」. 법률 규칙에는 근거 법조문·판례 이름 주석.

## 배포·목숨줄 검사(11/3)
- 배포는 맨 위 `deploy.bat` 하나로만 한다(문법 → DB 이주 → 환경 변수 이름 → 무대 배포 → 목숨줄 검사 → 올림 → 확인·되돌림). 건너뛰는 길을 만들지 않는다.
- 로그인·결제·환불·관리자 들어가기를 고치면 `node apps/web/check/lifeline.mjs` 초록 결과(6개 통과 줄)를 보고에 붙인다. 새 돈·로그인 길이 생기면 그 파일에 길을 더한다.
- 먼저 불리는 파일(공통 모듈·레이아웃·설정)이 나중에 불리는 파일의 값을 직접 건드리지 않는다. 필요한 값은 인자로 받거나 나중 파일이 먼저 것을 부른다(불리는 순서 탈 방지).

## 보고
- 짧게: 무엇을 바꿨고, 어떻게 확인했고, 남은 것(코워크에 넘길 일 포함)은 무엇인지. 한국어로.
