# 인천 채우기(11/4 대표님) — 한 번만 돌림. 철원 지우기·인천 법원 더하기(0033) → 인천 법정동 → 실거래 2년 → 인천 법원 물건·매각결과 → 공매 인천 물건(공매 결과는 이미 전국으로 받고 있음) → 건축물대장 → 분석 → 첫 화면 숫자
# 실행: powershell -ExecutionPolicy Bypass -File D:\Auction\auction-platform\scripts\fill-incheon.ps1
$ErrorActionPreference = 'Continue'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$env:PYTHONIOENCODING = 'utf-8'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
New-Item -ItemType Directory -Force -Path "$root\logs" | Out-Null
$log = "$root\logs\fill-incheon_{0}.log" -f (Get-Date -Format 'yyyyMMdd_HHmm')
$uv = (Get-Command uv -ErrorAction SilentlyContinue).Source
if (-not $uv) { $uv = "$env:USERPROFILE\.local\bin\uv.exe" }
$failed = @()
function Run($name, [string[]]$cmd) {
  Write-Host "── $name" -ForegroundColor Cyan
  & $uv run @cmd *>&1 | Tee-Object -FilePath $log -Append
  if ($LASTEXITCODE -ne 0) { $script:failed += $name; Write-Host "   $name 실패 — 다음 단계는 계속" -ForegroundColor Yellow }
}
Run "철원 지우기 · 인천 법원 더하기(0033)" @('python', 'tools/apply_sql.py', 'db/migrations/0033_cheorwon_out_incheon_court.sql')
Run "인천 법정동" @('python', '-m', 'aucs_workers.collectors.regions')
Run "인천 실거래 2년" @('python', '-m', 'aucs_workers.collectors.trades', '--sido', '인천광역시', '--months', '24')
Run "인천 법원 물건(앞으로 6주)" @('python', '-m', 'aucs_workers.collectors.court_items', '--court', 'B000240')
Run "인천 법원 매각결과(최근 1주)" @('python', '-m', 'aucs_workers.collectors.court_results', '--court', 'B000240')
Run "공매 인천 물건" @('python', '-m', 'aucs_workers.collectors.onbid')
Run "건축물대장" @('python', '-m', 'aucs_workers.collectors.buildings', '--cap', '3000')
Run "분석" @('python', '-m', 'aucs_workers.jobs.analyze', '--stale')
Run "첫 화면 숫자 새로" @('python', '-m', 'aucs_workers.jobs.warm')
Write-Host ""
if ($failed) { Write-Host "끝 · 실패: $($failed -join ', ') — 로그: $log" -ForegroundColor Yellow } else { Write-Host "끝 · 모두 통과 — 로그: $log" -ForegroundColor Green }
