# 서버 하나를 계속 켜 둡니다(꺼지면 5초 뒤 다시 켬). 작업 스케줄러가 로그인할 때 숨김으로 부릅니다.
# 코드가 바뀌면 API는 이 스크립트가 껐다 켜고(2초마다 확인), 웹은 next dev 가 스스로 다시 읽습니다.
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
    # uvicorn --reload 가 윈도우에서 「Reloading...」에 자주 멈춰서(10/18), 코드가 바뀌면 이 창이 직접 끄고 다시 켬
    # 실행 기록은 logs\server_api_run.log (다시 켤 때마다 새로 씀), 켜기·끄기 기록은 server_api.log
    $p = Start-Process -FilePath $uv -ArgumentList 'run', 'uvicorn', 'aucs_api.main:app', '--host', '0.0.0.0', '--port', '8100' `
      -WorkingDirectory $root -NoNewWindow -PassThru `
      -RedirectStandardOutput "$root\logs\server_api_out.log" -RedirectStandardError "$root\logs\server_api_run.log"
    $watch = @("$root\apps\api\src", "$root\packages\rules\src")
    function Get-Stamp { (Get-ChildItem $watch -Recurse -Filter *.py -ErrorAction SilentlyContinue | Measure-Object LastWriteTime -Maximum).Maximum }
    $stamp = Get-Stamp
    while (-not $p.HasExited) {
      Start-Sleep -Seconds 2
      $now = Get-Stamp
      if ($now -gt $stamp) {
        Start-Sleep -Seconds 1  # 여러 파일을 한꺼번에 고칠 때 잠깐 기다림
        "[$(Get-Date -Format 'MM-dd HH:mm:ss')] 코드 바뀜 — API 다시 켬" | Out-File -Append -Encoding utf8 $log
        taskkill /PID $p.Id /T /F 2>&1 | Out-Null
        break
      }
    }
  } else {
    # 새 꾸러미가 생기면(pnpm-lock.yaml 이 더 새로우면) 먼저 설치
    $mark = "$root\node_modules\.modules.yaml"
    if (-not (Test-Path $mark) -or (Get-Item "$root\pnpm-lock.yaml").LastWriteTime -gt (Get-Item $mark).LastWriteTime) {
      & $pnpm install 2>&1 | Out-File -Append -Encoding utf8 $log
    }
    & $pnpm dev:web 2>&1 | Out-File -Append -Encoding utf8 $log
  }
  "[$(Get-Date -Format 'MM-dd HH:mm:ss')] 꺼짐 — 다시 켬" | Out-File -Append -Encoding utf8 $log
  Start-Sleep -Seconds $(if ($Name -eq 'api') { 1 } else { 5 })
}
