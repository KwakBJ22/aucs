# 옥스 관리자 「다시 돌리기 요청」 확인 — 작업 스케줄러가 5분마다 부름(11/2). 요청이 없으면 몇 초 만에 끝남.
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$env:PYTHONIOENCODING = 'utf-8'
$uv = (Get-Command uv -ErrorAction SilentlyContinue).Source
if (-not $uv) { $uv = "$env:USERPROFILE\.local\bin\uv.exe" }
& $uv run python -m aucs_workers.jobs.requests *>&1 | Out-File -Append -Encoding utf8 "$root\logs\requests.log"
