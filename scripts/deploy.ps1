# 옥스 배포(11/3, 11/4 빠르게) — 이 순서만. 검사를 건너뛰는 길 없음.
#  11/4: 지난 배포 뒤 바뀐 쪽(웹·API)만 올림 · 무대 배포를 맨 처음 함께 시작하고 그동안 검사(손님 주소는 검사 통과 뒤에만)
#        · 설치된 vercel 을 바로 부름 · 환경 변수 이름은 .env 가 바뀌었거나 하루 지났을 때만 확인
#  1 커밋 안 된 파일 수 알림 → 2 문법 검사 → 3 DB 이주 확인 → 4 Vercel 환경 변수 이름 확인
#  5 API 무대 배포(주소만, 손님 주소는 그대로) + /health → 6 웹 무대 배포 + 목숨줄 검사
#  7 모두 초록이면 API → 웹 순서로 손님 주소에 올림 → 8 aucs.co.kr 확인, 실패하면 바로 되돌림 → 9 배포 기록
#  10 성공했을 때만 GitHub에 보관(커밋·올리기) — 실패하면 올리지 않음
# 비밀값은 화면·기록에 찍지 않습니다(.env 에서 읽기만).
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root
. "$PSScriptRoot\pgtools.ps1"

$stamp = Get-Date -Format "yyyyMMdd_HHmm"
New-Item -ItemType Directory -Force -Path "$root\logs" | Out-Null
$log = "$root\logs\deploy_$stamp.log"
Start-Transcript -Path $log -Append | Out-Null
$started = Get-Date
$apiDir = $root
$webDir = "$root\apps\web"
$state = @{ api = $null; web = $null; promoted = @() }

function Read-Env([string]$name) {
  $line = Get-Content "$root\.env" -Encoding UTF8 | Where-Object { $_ -match "^\s*$name\s*=" } | Select-Object -First 1
  if (-not $line) { return "" }
  return ($line -replace "^\s*$name\s*=\s*", '').Trim().Trim('"').Trim("'")
}

function Save-Run([string]$status, [string]$msg) {
  try {
    $m = $msg.Replace("'", "''")
    $sql = "insert into ops.job_runs (job_id, started_at, finished_at, status, message) values ('deploy', '$($started.ToString("o"))', now(), '$status', '$m');"
    $null = Invoke-PgSql (Get-DbUrl) $sql
  } catch { Write-Host "  (배포 기록을 DB에 남기지 못했어요 — 파일 기록은 $log)" }
}

function Stop-Deploy([string]$why) {
  Write-Host ""
  Write-Host "배포 멈춤 — $why" -ForegroundColor Red
  Save-Run 'failed' "멈춤: $why"
  Stop-Transcript | Out-Null
  exit 1
}

function Step([string]$title) { Write-Host ""; Write-Host "▶ $title" -ForegroundColor Cyan }

# Vercel CLI 는 안내 글을 오류 통로(stderr)로 내보냄 → PowerShell 5 가 「Stop」 설정에서 오류로 보고 멈춤(11/4).
# 대표가 로그인한 것과 같은 판(npx vercel)을 씀 — 최신판(@latest)은 로그인 정보를 다른 곳에서 찾아 「로그인 안 됨」(11/4).
# 이 호출 동안만 멈추지 않게 하고, 성공·실패는 끝난 번호($LASTEXITCODE)로만 판단.
$script:VercelExe = $null   # 설치된 vercel(대표 11/4 설치)이 로그인돼 있으면 그것, 아니면 npx(예전 방식)
function Vercel-Cmd {
  if ($script:VercelExe) { return $script:VercelExe }
  $g = (Get-Command vercel -ErrorAction SilentlyContinue)
  $script:VercelExe = @('npx', '--yes', 'vercel')
  if ($g) {
    $old = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
    try { $null = & $g.Source whoami 2>&1; if ($LASTEXITCODE -eq 0) { $script:VercelExe = @($g.Source) } } finally { $ErrorActionPreference = $old }
  }
  return $script:VercelExe
}
function Vercel([string]$dir, [string[]]$argv) {
  $cmd = Vercel-Cmd
  $exe = $cmd[0]; $pre = @($cmd | Select-Object -Skip 1)
  $old = $ErrorActionPreference
  $ErrorActionPreference = 'Continue'
  try {
    $out = & $exe @pre @argv --cwd $dir 2>&1 | ForEach-Object { "$_" }
    $code = $LASTEXITCODE
  } finally { $ErrorActionPreference = $old }
  return @{ code = $code; text = ($out | Out-String) }
}
# 무대 배포를 뒤에서 시작(검사와 함께 돎). 손님 주소는 건드리지 않음(--skip-domain).
function Start-Stage([string]$dir) {
  $cmd = Vercel-Cmd
  Start-Job -ArgumentList $cmd, $dir -ScriptBlock {
    param($cmd, $dir)
    $exe = $cmd[0]; $pre = @($cmd | Select-Object -Skip 1)
    $ErrorActionPreference = 'Continue'
    $out = & $exe @pre deploy --prod --skip-domain --yes --cwd $dir 2>&1 | ForEach-Object { "$_" }
    @{ code = $LASTEXITCODE; text = ($out | Out-String) }
  }
}
function Wait-Stage($job, [string]$name) {
  $r = Receive-Job -Job $job -Wait -AutoRemoveJob
  if ($r -is [array]) { $r = $r[-1] }
  $url = ([regex]::Matches("$($r.text)", 'https://[a-z0-9.-]+\.vercel\.app') | Select-Object -Last 1).Value
  if ($r.code -or -not $url) { Stop-Deploy "$name 무대 배포 실패`n$($r.text)" }
  return $url
}

function Get-Ok([string]$url, [string]$bypass) {
  $h = @{}
  if ($bypass) { $h['x-vercel-protection-bypass'] = $bypass }
  for ($i = 0; $i -lt 6; $i++) {
    try {
      $r = Invoke-WebRequest -Uri $url -Headers $h -UseBasicParsing -TimeoutSec 30
      if ($r.StatusCode -eq 200) { return $true }
    } catch { }
    Start-Sleep -Seconds 3
  }
  return $false
}

$bypassApi = Read-Env 'VERCEL_BYPASS_API'
if (-not $bypassApi) { $bypassApi = Read-Env 'VERCEL_AUTOMATION_BYPASS_SECRET' }
$bypassWeb = Read-Env 'VERCEL_BYPASS_WEB'
if (-not $bypassWeb) { $bypassWeb = Read-Env 'VERCEL_AUTOMATION_BYPASS_SECRET' }

# 0 ── 무엇이 바뀌었나(지난 배포 뒤) → 바뀐 쪽만 올림. 기록이 없거나 공통 파일이 바뀌면 둘 다.
$lastFile = "$root\logs\last_deploy.txt"
$last = if (Test-Path $lastFile) { (Get-Content $lastFile -TotalCount 1).Trim() } else { "" }
$changed = @()
$old = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
try {
  if ($last) { $null = git cat-file -e "$last^{commit}" 2>$null; if ($LASTEXITCODE) { $last = "" } }   # 기준 판을 못 찾으면 둘 다
  if ($last) { $changed += @(git diff --name-only $last HEAD 2>$null) }
  $changed += @(git status --porcelain 2>$null | ForEach-Object { $_.Substring(3).Trim('"') })
} finally { $ErrorActionPreference = $old }
$changed = @($changed | Where-Object { $_ } | Sort-Object -Unique)
$webRe = '^(apps/web/|pnpm-lock\.yaml|pnpm-workspace\.yaml|package\.json)'
$apiRe = '^(api/|apps/api/|packages/|workers/|requirements\.txt|vercel\.json|pyproject\.toml|uv\.lock)'
$bothRe = '^(\.vercelignore)'
$doWeb = (-not $last) -or [bool]($changed | Where-Object { $_ -match $webRe -or $_ -match $bothRe })
$doApi = (-not $last) -or [bool]($changed | Where-Object { $_ -match $apiRe -or $_ -match $bothRe })
if (-not $doWeb -and -not $doApi) { $doWeb = $true; $doApi = $true }   # 바뀐 게 없어 보이면 둘 다(안전한 쪽)
$what = (@('API', '웹') | Where-Object { ($_ -eq 'API' -and $doApi) -or ($_ -eq '웹' -and $doWeb) }) -join '·'
Step "0 올릴 것: $what"
$dirty = @(git status --porcelain 2>$null | Where-Object { $_ })
Write-Host "  커밋 안 된 파일 $($dirty.Count)개가 같이 올라갑니다"

# 1 ── 무대 배포를 먼저 뒤에서 시작(손님 주소는 아직 그대로) — 그동안 아래 검사
Step "1 무대 배포 시작(뒤에서)"
$jobApi = if ($doApi) { Start-Stage $apiDir } else { $null }
$jobWeb = if ($doWeb) { Start-Stage $webDir } else { $null }
Write-Host "  시작함 — 검사가 하나라도 빨강이면 손님 주소에 올리지 않습니다"

# 2 ── 문법 검사(바뀐 쪽)
Step "2 문법 검사"
if ($doWeb) {
  pnpm --filter web typecheck;                   if ($LASTEXITCODE) { Stop-Deploy "화면 타입 검사(tsc) 실패" }
  Get-ChildItem "$webDir\check" -Filter *.mjs | ForEach-Object {
    node --check $_.FullName;                    if ($LASTEXITCODE) { Stop-Deploy "$($_.Name) 문법 오류" }
  }
}
if ($doApi) {
  uv run python -m compileall -q api apps/api/src packages/rules/src workers/src | Out-Null
  if ($LASTEXITCODE) { Stop-Deploy "파이썬 문법 오류(compileall)" }
  uv run ruff check . --quiet;                   if ($LASTEXITCODE) { Stop-Deploy "ruff 검사 실패" }
}
Write-Host "  문법 통과"

# 3 ── DB 이주: 0030 이후 이주 파일이 운영 DB에 모두 적용됐는지
Step "3 DB 이주 확인"
Initialize-PgTools
$applied = & "$pgBin\psql.exe" -d (Get-DbUrl) -t -A -c "select name from supabase_migrations.schema_migrations"
if ($LASTEXITCODE) { Stop-Deploy "DB에 붙지 못했어요(이주 확인)" }
$missing = Get-ChildItem "$root\db\migrations" -Filter *.sql |
  Where-Object { [int]($_.BaseName.Substring(0, 4)) -ge 30 -and ($applied -notcontains $_.BaseName) } |
  ForEach-Object { $_.BaseName }
if ($missing) { Stop-Deploy "DB에 아직 안 올린 이주 파일: $($missing -join ', ')" }
Write-Host "  이주 모두 적용됨"

# 4 ── Vercel 환경 변수 이름(값은 안 봄)
Step "4 Vercel 환경 변수 이름"
$need = @{
  $apiDir = @('DATABASE_URL', 'SUPABASE_URL', 'SUPABASE_PUBLISHABLE_KEY', 'SUPABASE_SECRET_KEY', 'CRON_SECRET', 'VAPID_PUBLIC_KEY', 'VAPID_PRIVATE_KEY', 'VAPID_SUBJECT')
  $webDir = @('NEXT_PUBLIC_API_BASE_URL', 'NEXT_PUBLIC_SUPABASE_URL', 'NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY', 'NEXT_PUBLIC_VAPID_PUBLIC_KEY')
}
$envStamp = "$root\logs\env_checked.txt"
$envFresh = (Test-Path $envStamp) -and ((Get-Item $envStamp).LastWriteTime -gt (Get-Item "$root\.env").LastWriteTime) -and ((Get-Item $envStamp).LastWriteTime -gt (Get-Date).AddHours(-24))
$envDirs = @()
if (-not $envFresh) { if ($doApi) { $envDirs += $apiDir }; if ($doWeb) { $envDirs += $webDir } }
foreach ($dir in $envDirs) {
  $r = Vercel $dir @('env', 'ls', 'production')
  if ($r.code) { Stop-Deploy "Vercel 환경 변수 목록을 못 읽었어요($(Split-Path $dir -Leaf))`n$($r.text)" }
  $lack = $need[$dir] | Where-Object { $r.text -notmatch "(?m)^\s*$_\s" }
  if ($lack) { Stop-Deploy "Vercel에 없는 환경 변수($(Split-Path $dir -Leaf)): $($lack -join ', ')" }
}
if ($envFresh) { Write-Host "  .env 가 그대로이고 하루 안에 확인함 — 지난 확인 그대로" }
else { if ($doApi -and $doWeb) { Set-Content $envStamp (Get-Date -Format o) }; Write-Host "  환경 변수 이름 모두 있음" }

# 5 ── 무대 배포 받기 + 확인
Step "5 무대 배포 확인"
if ($doApi) {
  $state.api = Wait-Stage $jobApi "API"
  Write-Host "  API $($state.api)"
  if (-not (Get-Ok "$($state.api)/health" $bypassApi)) { Stop-Deploy "무대 API /health 가 응답하지 않아요" }
  Write-Host "  /health 정상"
}
if ($doWeb) {
  $state.web = Wait-Stage $jobWeb "웹"
  Write-Host "  웹 $($state.web)"
}

# 6 ── 목숨줄 검사(늘 돎) — 웹을 안 올리면 지금 손님 화면(aucs.co.kr)으로
Step "6 목숨줄 검사"
$lifeUrl = if ($doWeb) { $state.web } else { "https://aucs.co.kr" }
$env:LIFELINE_BYPASS = $(if ($doWeb) { $bypassWeb } else { "" })
node "$webDir\check\lifeline.mjs" $lifeUrl
$code = $LASTEXITCODE
Remove-Item Env:LIFELINE_BYPASS -ErrorAction SilentlyContinue
if ($code) { Stop-Deploy "목숨줄 검사 빨강(위 실패한 길 · 사진 apps\web\check\failed)" }

# 7 ── 손님 주소로 올림(API 먼저)
Step "7 손님 주소로 올림"
foreach ($p in @(@($apiDir, $state.api), @($webDir, $state.web)) | Where-Object { $_[1] }) {
  $r = Vercel $p[0] @('promote', $p[1], '--yes')
  if ($r.code) {
    foreach ($d in $state.promoted) { $null = Vercel $d @('rollback', '--yes') }
    Stop-Deploy "올리기 실패: $($p[1]) (먼저 올린 것은 되돌림)`n$($r.text)"
  }
  $state.promoted += $p[0]
}
Write-Host "  올림"

# 8 ── 배포 뒤 확인, 실패하면 되돌림
Step "8 aucs.co.kr 확인"
$okWeb = Get-Ok "https://aucs.co.kr/health" ""
$okApi = Get-Ok "https://api.aucs.co.kr/health" ""
if (-not ($okWeb -and $okApi)) {
  Write-Host "  확인 실패 → 바로 앞 배포로 되돌립니다" -ForegroundColor Yellow
  foreach ($d in $state.promoted) { $null = Vercel $d @('rollback', '--yes') }
  Stop-Deploy "배포 뒤 확인 실패(웹 $okWeb · API $okApi) — 되돌렸어요"
}
Write-Host "  aucs.co.kr · api.aucs.co.kr 정상"

# 9 ── 기록
$sec = [int]((Get-Date) - $started).TotalSeconds
$msg = "배포 완료 ${sec}초($what) · 커밋 안 된 파일 $($dirty.Count)개 · API $($state.api) · 웹 $($state.web)"
Save-Run 'ok' $msg

# 10 ── GitHub 보관(배포가 성공한 판만). 여기서 실패해도 배포는 이미 끝났으니 알림만.
Step "10 GitHub 보관"
$old = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
try {
  if ($dirty.Count -gt 0) {
    git add -A | Out-Null
    git commit -q -m ("배포 " + $started.ToString("yyyy-MM-dd HH:mm") + " · 검사 통과") | Out-Null
  }
  git push -q origin main 2>&1 | Out-Null
  if ($LASTEXITCODE) { Write-Host "  GitHub에 올리지 못했어요(배포는 끝남) — 다음 배포 때 같이 올라가요" -ForegroundColor Yellow }
  else { Write-Host "  GitHub에 올림" }
} finally { $ErrorActionPreference = $old }
# 다음 배포가 「바뀐 쪽」을 가릴 기준(이번에 올린 판)
try { Set-Content $lastFile (git rev-parse HEAD) } catch { }
Write-Host ""
Write-Host $msg -ForegroundColor Green
Stop-Transcript | Out-Null
exit 0
