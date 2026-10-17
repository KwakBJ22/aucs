# 옥스 (aucs)

부동산 경매 정보 서비스. 휴대폰 우선 웹 + PC 전문가 보기.

## 처음 켜는 법 (Windows PowerShell)
필요한 것: Node 22, pnpm(`npm i -g pnpm`), uv.

```powershell
cd D:\Auction\auction-platform
# 1) .env 확인 (.env.example 을 보고 값 넣기 — 저장소에 올리지 않음)
# 2) 설치 (VM에서 설치한 것이 있으면 Windows에서 한 번 다시 설치)
uv sync
pnpm install
# 3) API 켜기 (창 하나)
uv run uvicorn aucs_api.main:app --port 8100
# 4) 웹 켜기 (다른 창)
pnpm dev:web
```
브라우저에서 http://localhost:3000 → 「API 연결 정상 / DB 연결 정상」이면 준비 끝.

## 검사
```powershell
.\scripts\check.ps1
```

## 폴더
`docs/design/07-folders.md` 참고. 작업 규칙은 `CLAUDE.md`, 용어는 `docs/glossary.md`.
