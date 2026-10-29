# 옥스 핵심 흐름 자동 검사(출시 전 꼭, 10/29) — 켜 둔 화면(3000)·API(8100)를 이 PC의 크롬으로 한 바퀴 돌림.
#   휴대폰: 말로 찾기 → 경매 상세 → 입찰가 계산 → 보고서 → 공매 상세 → (시험 회원 로그인) 관심 담기·빼기 → 모의입찰 남기기·지우기 → 내 경매
#   PC: 전체 물건 표(옆으로 밀리지 않음·줄 고르기·공매만) → 시장
# 실행: powershell -ExecutionPolicy Bypass -File D:\Auction\auction-platform\scripts\flow-test.ps1
# 고칠 때마다 한 번 돌리면 망가진 곳이 바로 보임. 시험 회원(e2e-test@aucs.co.kr)은 시험 뒤 흔적을 지움.
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
foreach ($u in 'http://localhost:8100/health', 'http://localhost:3000/') {
  try { Invoke-WebRequest -Uri $u -UseBasicParsing -TimeoutSec 60 | Out-Null }
  catch { Write-Host "$u 가 안 열립니다 — scripts\serve.ps1 로 서버를 먼저 켜 주세요"; exit 1 }
}
if (-not (Test-Path "$root\apps\web\node_modules\@playwright\test")) {
  Write-Host '검사 도구 설치(처음 한 번)...'
  pnpm install --frozen-lockfile
}
New-Item -ItemType Directory -Force -Path "$root\logs" | Out-Null
$log = "$root\logs\flow_test_$(Get-Date -Format 'yyyyMMdd_HHmm').log"
pnpm --filter web e2e 2>&1 | Tee-Object -FilePath $log
if ($LASTEXITCODE -ne 0) { Write-Host "`n확인 필요 — 로그: $log (실패한 화면 기록은 apps\web\test-results)"; exit 1 }
Write-Host "`n핵심 흐름 통과 — 로그: $log"
