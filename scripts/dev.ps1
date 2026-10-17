# 화면 보기: API(8100)와 웹(3000)을 각각 새 창으로 켜고 브라우저를 엽니다. 끌 때는 두 창을 닫으면 됩니다.
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root
if (-not (Get-Command pnpm -ErrorAction SilentlyContinue)) { npm i -g pnpm | Out-Null }
if (-not (Test-Path "$root\node_modules")) { pnpm install }
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$root'; `$env:PYTHONIOENCODING='utf-8'; uv run uvicorn aucs_api.main:app --port 8100"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$root'; pnpm dev:web"
Start-Sleep -Seconds 12
Start-Process "http://localhost:3000"
