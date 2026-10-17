# 서버 하나를 계속 켜 둡니다(꺼지면 5초 뒤 다시 켬). 작업 스케줄러가 로그인할 때 숨김으로 부릅니다.
# 코드가 바뀌면 API·웹 모두 스스로 다시 읽으므로 따로 껐다 켤 필요 없습니다.
param([Parameter(Mandatory = $true)][ValidateSet('api', 'web')][string]$Name)
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
New-Item -ItemType Directory -Force -Path "$root\logs" | Out-Null
$log = "$root\logs\server_$Name.log"
$env:PYTHONIOENCODING = 'utf-8'
$uv = (Get-Command uv -ErrorAction SilentlyContinue).Source
if (-not $uv) { $uv = "$env:USERPROFILE\.local\bin\uv.exe" }
$pnpm = (Get-Command pnpm -ErrorAction SilentlyContinue).Source
if (-not $pnpm) { $pnpm = "$env:APPDATA\npm\pnpm.cmd" }
while ($true) {
  "[$(Get-Date -Format 'MM-dd HH:mm:ss')] 켜기" | Out-File -Append -Encoding utf8 $log
  if ($Name -eq 'api') {
    & $uv sync --all-packages 2>&1 | Out-File -Append -Encoding utf8 $log
    & $uv run uvicorn aucs_api.main:app --port 8100 --reload --reload-dir apps/api/src --reload-dir packages/rules/src --timeout-graceful-shutdown 2 2>&1 | Out-File -Append -Encoding utf8 $log
  } else {
    # 새 꾸러미가 생기면(pnpm-lock.yaml 이 더 새로우면) 먼저 설치
    $mark = "$root\node_modules\.modules.yaml"
    if (-not (Test-Path $mark) -or (Get-Item "$root\pnpm-lock.yaml").LastWriteTime -gt (Get-Item $mark).LastWriteTime) {
      & $pnpm install 2>&1 | Out-File -Append -Encoding utf8 $log
    }
    & $pnpm dev:web 2>&1 | Out-File -Append -Encoding utf8 $log
  }
  "[$(Get-Date -Format 'MM-dd HH:mm:ss')] 꺼짐 — 5초 뒤 다시 켬" | Out-File -Append -Encoding utf8 $log
  Start-Sleep -Seconds 5
}
