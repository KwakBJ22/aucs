# 07 개발 폴더와 소스

저장소 하나에 화면·API·수집·규칙·DB 이주 파일·문서를 모두 둡니다. 분석 규칙은 화면·API와 분리된 패키지로 둡니다.

```text
auction-platform/
├─ apps/
│  ├─ web/                 # Next.js 화면 (휴대폰 우선 + PC + 관리자)
│  │  ├─ app/              # 화면(라우트): (tabs)/home, find, watch, me · item/[id] · calc · bid · field · admin
│  │  ├─ components/       # 카드, 신호등, 바텀시트, 슬라이더, 지도 …
│  │  ├─ lib/              # API 호출, 금액·날짜 표시, 용어사전, copy.ko.ts
│  │  └─ public/           # 아이콘, manifest(홈 화면 추가), service worker(푸시)
│  └─ api/                 # FastAPI
│     ├─ app/
│     │  ├─ routers/       # items, calc, bid_forms, me, payments, admin
│     │  ├─ schemas/       # 요청·응답 모양(Pydantic)
│     │  ├─ services/      # 화면용 조합, 공개 설정 걸러내기
│     │  └─ auth/          # 카카오 로그인, 권한
│     └─ tests/
├─ workers/
│  ├─ collectors/          # court_items, court_docs, court_results, trades, buildings, price_notice, land_use, redev, kapt
│  ├─ extract/             # PDF·OCR 읽기, 항목 추출, 교차검증, 글자 오류 보정 사전
│  ├─ jobs/                # 작업 예약·대기열·재시도, notify(알림)
│  └─ tests/
├─ packages/
│  └─ rules/               # 분석 규칙(순수 Python): rights, tenants, distribution, price, sale_rate, risk, costs, schedule, bid_form_check
│     └─ tests/cases/      # 실제 사건 정답 사례 (예: 2025타경55580.json)
├─ db/
│  ├─ migrations/          # 스키마 이주 파일 (번호순, 코워크 담당)
│  └─ seed/                # 기준표(소액임차·세율·LTV), 법원·지역 목록
├─ infra/
│  ├─ docker-compose.yml   # 내 PC용
│  ├─ docker-compose.prod.yml
│  └─ scripts/             # 백업·복구·서버 준비
├─ tools/duckdb_export/    # 로컬 DuckDB에서 다시 못 받는 자료만 한 번 옮기기 (코워크 담당)
├─ docs/                   # 설계 요약, 용어사전, 운영 절차
├─ CLAUDE.md
├─ .env.example
└─ README.md
```

## 주요 소스와 단계
| 위치 | 파일 | 역할 | 단계 |
|---|---|---|---|
| packages/rules | rights.py | 말소기준·소멸/인수 판정 | 1 |
| packages/rules | tenants.py | 대항력·우선변제·최우선·가족 임차인 | 1 |
| packages/rules | distribution.py | 예상 배당 | 1 |
| packages/rules | price.py | 비교 거래 선택·층 보정·기준 시세 | 1 |
| packages/rules | sale_rate.py | 낙찰가율 분포·예상 낙찰가 범위 | 1 |
| packages/rules | risk.py | 위험 신호 목록·등급 | 1 |
| packages/rules | costs.py | 취득세·등기비·명도비·대출·필요한 현금 | 3 |
| packages/rules | schedule.py | 종결 일정 예측 | 3 |
| packages/rules | bid_form_check.py | 입찰표 검사, 금액 한글 읽기 | 4 |
| workers/collectors | court_items.py 등 | 원천별 수집(원천 하나 = 파일 하나) | 1 |
| workers/extract | registry.py, spec_sheet.py, status_report.py, doc_events.py | 등기·명세서·현황조사서·문건 추출 | 1 |
| workers/extract | fix_dictionary.py | 글자 오류 보정 사전 | 1 |
| workers/jobs | scheduler.py, notify.py | 작업 예약, 알림 | 1, 4 |
| apps/api | routers/*.py | API 명세의 주소 | 2~5 |
| apps/web | app/** | 화면 설계의 화면 ID와 1:1 | 2~5 |
| db | migrations/0001_init.sql … | 데이터 설계의 표 | 1 |

## 지금 코드(D:\Auction\system)에서 옮길 것 — 1단계
| 지금 | 새 위치 | 방법 |
|---|---|---|
| collectors/court_auction.py | workers/collectors/court_items.py, court_results.py | 요청 모양·속도·중단 규칙 그대로, 저장은 PostgreSQL raw로 |
| court_docs, tessdata | workers/collectors/court_docs.py, workers/extract/ | 추출 결과에 원문 위치·신뢰도·검증 상태 추가 |
| db/views.py 문건흐름·문건신호 | workers/extract/doc_events.py, packages/rules/risk.py | SQL 뷰를 규칙 함수로, 시험 사례 추가 |
| collectors/case_pool.py | packages/rules/sale_rate.py | 지지옥션 출처는 빼고 |
| db/load_정비사업장.py, redev_download.py | workers/collectors/redev.py | 그대로 |
| 실거래·건축물대장·공시가격 | workers/collectors/ | 그대로 |
| web/ | 참고만 | Next.js로 새로. 권리 사다리·사건 흐름·배당 폭포의 생각은 가져옴 |
| tasks/*.ps1 | workers/jobs/scheduler.py | 서버 안 작업 예약으로 |

지금 시스템은 새 시스템이 같은 결과를 낼 때까지 그대로 둡니다(읽기만).
