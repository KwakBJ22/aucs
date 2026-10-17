# SQL 파일 하나 적용: .\scripts\apply-sql.ps1 db\migrations\0004_trim_trades_index.sql
param([Parameter(Mandatory = $true)][string]$File)
Set-Location (Split-Path $PSScriptRoot -Parent)
uv run python tools/apply_sql.py $File
