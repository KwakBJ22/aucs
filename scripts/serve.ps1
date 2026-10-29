# 서버 하나를 계속 켜 둡니다(꺼지면 5초 뒤 다시 켬). 작업 스케줄러가 로그인할 때 숨김으로 부릅니다.
# 코드가 바뀌면 API는 이 스크립트가 껐다 켜고(2초마다 확인), 웹은 next dev 가 스스로 다시 읽습니다. 웹 실행 기록은 logs\server_web_run.log.
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
    # 10/29: 가장 늦은 수정 시각만 보면 새 파일(복사로 옛 시각)·지운 파일을 놓침 → 파일 수 + 수정 시각 합으로 비교, .env 도 봄
    function Get-Stamp {
      $f = @(Get-ChildItem $watch -Recurse -Filter *.py -ErrorAction SilentlyContinue) + @(Get-Item "$root\.env" -ErrorAction SilentlyContinue)
      "{0}|{1}" -f $f.Count, ($f | ForEach-Object { $_.LastWriteTimeUtc.Ticks } | Measure-Object -Sum).Sum
    }
    $stamp = Get-Stamp
    while (-not $p.HasExited) {
      Start-Sleep -Seconds 2
      $now = Get-Stamp
      if ($now -ne $stamp) {
        Start-Sleep -Seconds 1  # 여러 파일을 한꺼번에 고칠 때 잠깐 기다림
        "[$(Get-Date -Format 'MM-dd HH:mm:ss')] 코드 바뀜 — API 다시 켬" | Out-File -Append -Encoding utf8 $log
        taskkill /PID $p.Id /T /F 2>&1 | Out-Null
        # 끈 뒤에도 8100 을 쥔 프로그램이 남으면 새로 켤 때 「주소 사용 중」으로 바로 꺼짐 → 비워질 때까지(최대 10초) 기다리고, 남으면 끔
        for ($i = 0; $i -lt 10; $i++) {
          $held = Get-NetTCPConnection -LocalPort 8100 -State Listen -ErrorAction SilentlyContinue
          if (-not $held) { break }
          Start-Sleep -Seconds 1
        }
        if ($held) { $held | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue } }
        break
      }
    }
  } else {
    # 새 꾸러미가 생기면(pnpm-lock.yaml 이 더 새로우면) 먼저 설치
    $mark = "$root\node_modules\.modules.yaml"
    if (-not (Test-Path $mark) -or (Get-Item "$root\pnpm-lock.yaml").LastWriteTime -gt (Get-Item $mark).LastWriteTime) {
      & $pnpm install 2>&1 | Out-File -Append -Encoding utf8 $log
    }
    # 10/18 저녁: `pnpm dev:web | Out-File` 로 켜면 창 없이 돌 때 next 가 오류 글 없이 40초쯤 뒤 꺼지기를 되풀이함
    # → API처럼 node 로 next 를 직접 켜고 출력은 파일로 바로 남김 (실행 기록 logs\server_web_run.log, 오류 logs\server_web_err.log)
    $node = (Get-Command node -ErrorAction SilentlyContinue).Source
    if (-not $node) { $node = "$env:ProgramFiles\nodejs\node.exe" }
    # 10/27: 터보팩으로 켜서 화면 첫 열기(옮겨 엮기)를 빠르게 함(예전 상세 화면 첫 열기 약 30초).
    #        터보팩으로 켠 뒤 1분 안에 꺼지면 다음부터는 예전 방식으로 켬.
    # 10/29: 「빠른 보기」 — scripts\web-mode.txt 가 fast 면 미리 만들어(build) 실제 서비스 방식(start)으로 켬.
    #        화면 첫 열기가 몇 초 → 1초 안쪽. 코드를 고치면 web-mode.ps1 fast 로 다시 만들어야 반영됨.
    $mode = if (Test-Path "$root\scripts\web-mode.txt") { (Get-Content "$root\scripts\web-mode.txt" -Raw).Trim() } else { 'dev' }
    if ($mode -eq 'fast') {
      $env:NEXT_DIST_DIR = '.next-fast'
      "[$(Get-Date -Format 'MM-dd HH:mm:ss')] 빠른 보기: 만드는 중(1~2분)" | Out-File -Append -Encoding utf8 $log
      $b = Start-Process -FilePath $node -ArgumentList 'node_modules\next\dist\bin\next', 'build' `
        -WorkingDirectory "$root\apps\web" -NoNewWindow -PassThru -Wait `
        -RedirectStandardOutput "$root\logs\server_web_build.log" -RedirectStandardError "$root\logs\server_web_build_err.log"
      if ($b.ExitCode -eq 0) {
        "[$(Get-Date -Format 'MM-dd HH:mm:ss')] 빠른 보기: 다 만듦 — 켬" | Out-File -Append -Encoding utf8 $log
        $nextArgs = @('node_modules\next\dist\bin\next', 'start', '-p', '3000')
      } else {
        "[$(Get-Date -Format 'MM-dd HH:mm:ss')] 빠른 보기 만들기 실패 — 개발 방식으로 켬 (logs\server_web_build_err.log)" | Out-File -Append -Encoding utf8 $log
        Remove-Item Env:NEXT_DIST_DIR -ErrorAction SilentlyContinue
        $mode = 'dev'
      }
    }
    if ($mode -ne 'fast') {
      Remove-Item Env:NEXT_DIST_DIR -ErrorAction SilentlyContinue
      $nextArgs = @('node_modules\next\dist\bin\next', 'dev', '-p', '3000')
      if (-not $script:noTurbo) { $nextArgs += '--turbopack' }
    }
    $started = Get-Date
    $p = Start-Process -FilePath $node -ArgumentList $nextArgs `
      -WorkingDirectory "$root\apps\web" -NoNewWindow -PassThru `
      -RedirectStandardOutput "$root\logs\server_web_run.log" -RedirectStandardError "$root\logs\server_web_err.log"
    $p.WaitForExit()
    "[$(Get-Date -Format 'MM-dd HH:mm:ss')] next 끝남(코드 $($p.ExitCode)) — 오류는 server_web_err.log" | Out-File -Append -Encoding utf8 $log
    if ($mode -ne 'fast' -and -not $script:noTurbo -and ((Get-Date) - $started).TotalSeconds -lt 60) {
      $script:noTurbo = $true
      "[$(Get-Date -Format 'MM-dd HH:mm:ss')] 터보팩으로 바로 꺼짐 — 예전 방식으로 켬" | Out-File -Append -Encoding utf8 $log
    }
  }
  "[$(Get-Date -Format 'MM-dd HH:mm:ss')] 꺼짐 — 다시 켬" | Out-File -Append -Encoding utf8 $log
  Start-Sleep -Seconds $(if ($Name -eq 'api') { 1 } else { 5 })
}
