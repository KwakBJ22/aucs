# 정비사업 넣기 + 실거래 수집기 시험(아파트 매매 이번 달만)
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
$env:PYTHONIOENCODING = 'utf-8'
Write-Host "1/2 정비사업"; & "$PSScriptRoot\load-redev.ps1"
Write-Host "2/2 실거래 시험 (아파트 매매 이번 달)"; uv run python -m aucs_workers.collectors.trades --types apt_sale --months 1
Write-Host "끝"
