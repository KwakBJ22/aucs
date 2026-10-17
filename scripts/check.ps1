# 형식·타입·시험을 한 번에 돌립니다 (Windows PowerShell).
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
uv run ruff check .;               if ($LASTEXITCODE) { exit 1 }
uv run ruff format --check .;      if ($LASTEXITCODE) { exit 1 }
uv run mypy packages/rules/src apps/api/src; if ($LASTEXITCODE) { exit 1 }
uv run pytest -q;                  if ($LASTEXITCODE) { exit 1 }
pnpm --filter web check;           if ($LASTEXITCODE) { exit 1 }
Write-Host "검사 통과"
