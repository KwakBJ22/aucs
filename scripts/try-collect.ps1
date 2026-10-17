# 새 수집기 시험 한 번 (서울중앙 물건·매각결과 + 사건 하나 서류 + 분석). 법원 사이트에 천천히 요청합니다.
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
$env:PYTHONIOENCODING = "utf-8"
Write-Host "1/4 물건 (서울중앙)"; uv run python -m aucs_workers.collectors.court_items --test
Write-Host "2/4 매각결과 (서울중앙)"; uv run python -m aucs_workers.collectors.court_results --test
Write-Host "3/4 사건 서류 (수원 2025타경55580)"; uv run python -m aucs_workers.collectors.court_docs --case B000250 2025타경55580
Write-Host "4/4 분석"; uv run python -m aucs_workers.jobs.analyze
Write-Host "끝"
