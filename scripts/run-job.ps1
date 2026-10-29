# 옥스 수집·분석 실행기 — 작업 스케줄러가 부릅니다. 결과는 logs\ 에 남깁니다.
param([Parameter(Mandatory = $true)][ValidateSet('items', 'results', 'docs', 'analyze', 'notify', 'morning', 'daily', 'trades', 'redev', 'buildings', 'buildings_retry', 'onbid', 'onbid_first', 'watched')][string]$Job)
$ErrorActionPreference = 'Continue'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
New-Item -ItemType Directory -Force -Path "$root\logs" | Out-Null
$log = "$root\logs\{0}_{1}.log" -f $Job, (Get-Date -Format 'yyyyMMdd_HHmm')
$env:PYTHONIOENCODING = 'utf-8'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8  # 창에 한글이 깨지지 않게(10/28)
$uv = (Get-Command uv -ErrorAction SilentlyContinue).Source
if (-not $uv) { $uv = "$env:USERPROFILE\.local\bin\uv.exe" }
$mod = @{ items = 'aucs_workers.collectors.court_items'; results = 'aucs_workers.collectors.court_results';
          docs = 'aucs_workers.collectors.court_docs --archive'; analyze = 'aucs_workers.jobs.analyze'; notify = 'aucs_workers.jobs.notify'; morning = 'aucs_workers.jobs.notify --morning'; daily = 'aucs_workers.jobs.daily'; trades = 'aucs_workers.collectors.trades --months 3'; redev = 'aucs_workers.collectors.redev'; buildings = 'aucs_workers.collectors.buildings --cap 3000'; buildings_retry = 'aucs_workers.collectors.buildings --retry-none --cap 3000'; onbid = 'aucs_workers.collectors.onbid'; onbid_first = 'aucs_workers.collectors.onbid --result-days 60'; watched = 'aucs_workers.jobs.watched' }[$Job]
$parts = $mod -split ' '
# 공매 처음 한 번: 받아 둔 DuckDB 입찰결과(5/4~9/2)를 먼저 옮긴 뒤 수집(10/28)
if ($Job -eq 'onbid_first') { & $uv run --with duckdb python tools/duckdb_export/export_onbid_results.py *>&1 | Tee-Object -FilePath $log }
& $uv run python -m @parts *>&1 | Tee-Object -FilePath $log -Append
if ($LASTEXITCODE -ne 0) {
  Add-Type -AssemblyName System.Windows.Forms
  [System.Windows.Forms.MessageBox]::Show("옥스 $Job 작업이 멈췄습니다.`n`n로그: $log`n`n코워크에 알려 주세요.", '옥스 — 수집 확인') | Out-Null
}
