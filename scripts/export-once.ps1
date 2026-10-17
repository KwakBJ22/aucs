# 로컬 DuckDB → Supabase 한 번 옮기기 (수 분 걸림)
Set-Location (Split-Path $PSScriptRoot -Parent)
uv run --with duckdb python tools/duckdb_export/export_once.py
