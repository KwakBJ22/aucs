# 정비사업 넣기: 받아 둔 사업장 목록 엑셀 + 지금 시스템의 구역 추진현황 (한 번)
Set-Location (Split-Path $PSScriptRoot -Parent)
$env:PYTHONIOENCODING = 'utf-8'
$xls = Get-ChildItem 'D:\Auction\data\정비사업\*.xls' | Sort-Object LastWriteTime | Select-Object -Last 1
uv run python -m aucs_workers.collectors.redev --file $xls.FullName
uv run --with duckdb python tools/duckdb_export/export_redev_zones.py
