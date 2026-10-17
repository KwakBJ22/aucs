# 옥스 수집·분석 실행기 — 작업 스케줄러가 부릅니다. 결과는 logs\ 에 남깁니다.
param([Parameter(Mandatory = $true)][ValidateSet('items', 'results', 'docs', 'analyze', 'notify', 'trades', 'redev')][string]$Job)
$ErrorActionPreference = 'Continue'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
New-Item -ItemType Directory -Force -Path "$root\logs" | Out-Null
$log = "$root\logs\{0}_{1}.log" -f $Job, (Get-Date -Format 'yyyyMMdd_HHmm')
$env:PYTHONIOENCODING = 'utf-8'
$uv = (Get-Command uv -ErrorAction SilentlyContinue).Source
if (-not $uv) { $uv = "$env:USERPROFILE\.local\bin\uv.exe" }
$mod = @{ items = 'aucs_workers.collectors.court_items'; results = 'aucs_workers.collectors.court_results';
          docs = 'aucs_workers.collectors.court_docs --archive'; analyze = 'aucs_workers.jobs.analyze'; notify = 'aucs_workers.jobs.notify'; trades = 'aucs_workers.collectors.trades --months 3'; redev = 'aucs_workers.collectors.redev' }[$Job]
$parts = $mod -split ' '
& $uv run python -m @parts *>&1 | Tee-Object -FilePath $log
if ($LASTEXITCODE -ne 0) {
  Add-Type -AssemblyName System.Windows.Forms
  [System.Windows.Forms.MessageBox]::Show("옥스 $Job 작업이 멈췄습니다.`n`n로그: $log`n`n코워크에 알려 주세요.", '옥스 — 수집 확인') | Out-Null
}
