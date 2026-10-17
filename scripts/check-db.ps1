# DB 연결만 확인합니다 (Windows PowerShell).
Set-Location (Split-Path $PSScriptRoot -Parent)
uv sync -q
uv run python -c "from aucs_api.services.health import check_db; r=check_db(); print('DB 연결 정상 - PostGIS', r['postgis']) if r['ok'] else print('DB 연결 안 됨:', r['reason'])"
