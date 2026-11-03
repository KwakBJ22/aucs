# 옥스 배포(11/3) — 이 순서만. 건너뛰는 길 없음.
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
function Vercel([string]$dir, [string[]]$argv) {
  $old = $ErrorActionPreference
  $ErrorActionPreference = 'Continue'
  try {
    $out = & npx --yes vercel @argv --cwd $dir 2>&1 | ForEach-Object { "$_" }
    $code = $LASTEXITCODE
  } finally { $ErrorActionPreference = $old }
  return @{ code = $code; text = ($out | Out-String) }
}

function Get-Ok([string]$url, [string]$bypass) {
  $h = @{}
  if ($bypass) { $h['x-vercel-protection-bypass'] = $bypass }
  for ($i = 0; $i -lt 3; $i++) {
    try {
      $r = Invoke-WebRequest -Uri $url -Headers $h -UseBasicParsing -TimeoutSec 30
      if ($r.StatusCode -eq 200) { return $true }
    } catch { }
    Start-Sleep -Seconds 10
  }
  return $false
}

$bypassApi = Read-Env 'VERCEL_BYPASS_API'
if (-not $bypassApi) { $bypassApi = Read-Env 'VERCEL_AUTOMATION_BYPASS_SECRET' }
$bypassWeb = Read-Env 'VERCEL_BYPASS_WEB'
if (-not $bypassWeb) { $bypassWeb = Read-Env 'VERCEL_AUTOMATION_BYPASS_SECRET' }

# 1 ── 커밋 안 된 파일
Step "1 커밋 안 된 파일"
$dirty = @(git status --porcelain 2>$null | Where-Object { $_ })
Write-Host "  커밋 안 된 파일 $($dirty.Count)개가 같이 올라갑니다"

# 2 ── 문법 검사
Step "2 문법 검사"
pnpm --filter web typecheck;                     if ($LASTEXITCODE) { Stop-Deploy "화면 타입 검사(tsc) 실패" }
Get-ChildItem "$webDir\check" -Filter *.mjs | ForEach-Object {
  node --check $_.FullName;                      if ($LASTEXITCODE) { Stop-Deploy "$($_.Name) 문법 오류" }
}
uv run python -m compileall -q api apps/api/src packages/rules/src workers/src | Out-Null
if ($LASTEXITCODE) { Stop-Deploy "파이썬 문법 오류(compileall)" }
uv run ruff check . --quiet;                     if ($LASTEXITCODE) { Stop-Deploy "ruff 검사 실패" }
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
foreach ($dir in @($apiDir, $webDir)) {
  $r = Vercel $dir @('env', 'ls', 'production')
  if ($r.code) { Stop-Deploy "Vercel 환경 변수 목록을 못 읽었어요($(Split-Path $dir -Leaf))`n$($r.text)" }
  $lack = $need[$dir] | Where-Object { $r.text -notmatch "(?m)^\s*$_\s" }
  if ($lack) { Stop-Deploy "Vercel에 없는 환경 변수($(Split-Path $dir -Leaf)): $($lack -join ', ')" }
}
Write-Host "  환경 변수 이름 모두 있음"

# 5 ── API 무대 배포(손님 주소는 아직 그대로)
Step "5 API 무대 배포"
$r = Vercel $apiDir @('deploy', '--prod', '--skip-domain', '--yes')
$state.api = ([regex]::Matches($r.text, 'https://[a-z0-9.-]+\.vercel\.app') | Select-Object -Last 1).Value
if ($r.code -or -not $state.api) { Stop-Deploy "API 배포 실패`n$($r.text)" }
Write-Host "  $($state.api)"
if (-not (Get-Ok "$($state.api)/health" $bypassApi)) { Stop-Deploy "무대 API /health 가 응답하지 않아요" }
Write-Host "  /health 정상"

# 6 ── 웹 무대 배포 + 목숨줄 검사
Step "6 웹 무대 배포 + 목숨줄 검사"
$r = Vercel $webDir @('deploy', '--prod', '--skip-domain', '--yes')
$state.web = ([regex]::Matches($r.text, 'https://[a-z0-9.-]+\.vercel\.app') | Select-Object -Last 1).Value
if ($r.code -or -not $state.web) { Stop-Deploy "웹 배포 실패`n$($r.text)" }
Write-Host "  $($state.web)"
$env:LIFELINE_BYPASS = $bypassWeb
node "$webDir\check\lifeline.mjs" $state.web
$code = $LASTEXITCODE
Remove-Item Env:LIFELINE_BYPASS -ErrorAction SilentlyContinue
if ($code) { Stop-Deploy "목숨줄 검사 빨강(위 실패한 길 · 사진 apps\web\check\failed)" }

# 7 ── 손님 주소로 올림(API 먼저)
Step "7 손님 주소로 올림"
foreach ($p in @(@($apiDir, $state.api), @($webDir, $state.web))) {
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
Start-Sleep -Seconds 5
$okWeb = Get-Ok "https://aucs.co.kr/health" ""
$okApi = Get-Ok "https://api.aucs.co.kr/health" ""
if (-not ($okWeb -and $okApi)) {
  Write-Host "  확인 실패 → 바로 앞 배포로 되돌립니다" -ForegroundColor Yellow
  foreach ($d in @($webDir, $apiDir)) { $null = Vercel $d @('rollback', '--yes') }
  Stop-Deploy "배포 뒤 확인 실패(웹 $okWeb · API $okApi) — 되돌렸어요"
}
Write-Host "  aucs.co.kr · api.aucs.co.kr 정상"

# 9 ── 기록
$sec = [int]((Get-Date) - $started).TotalSeconds
$msg = "배포 완료 ${sec}초 · 커밋 안 된 파일 $($dirty.Count)개 · API $($state.api) · 웹 $($state.web)"
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
Write-Host ""
Write-Host $msg -ForegroundColor Green
Stop-Transcript | Out-Null
exit 0
