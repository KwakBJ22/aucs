# 옥스 DB 복구 시험 — 최근 백업(또는 -Dump 로 고른 것)을 이 PC 안의 임시 DB에 실제로 되살리고, 표마다 줄 수가 백업 때와 같은지 맞춰 봄.
# 운영 DB(Supabase)는 건드리지 않음. 끝나면 임시 DB는 지움. 30분~1시간(서류 원문이 큼).
# 실행: powershell -ExecutionPolicy Bypass -File D:\Auction\auction-platform\scripts\restore-test.ps1
# PostGIS 는 깔지 않음: 좌표 칸(geography)은 글자 칸으로 받아 줄 수만 맞춰 봄(좌표 색인 2개는 만들지 못해도 정상).
param([string]$Dump = '')
$ErrorActionPreference = 'Continue'  # 바깥 프로그램이 안내 글을 오류 칸에 써도 멈추지 않게(끝 코드로 판단)
. "$PSScriptRoot\pgtools.ps1"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PGCLIENTENCODING = 'UTF8'
$dir = Join-Path (Split-Path -Parent $root) 'backup'
if (-not $Dump) {
  $Dump = (Get-ChildItem $dir -Filter 'aucs_*.dump' | Where-Object { $_.Name -notlike '*.auth.dump' } | Sort-Object Name -Descending | Select-Object -First 1).FullName
}
if (-not $Dump -or -not (Test-Path $Dump)) { Write-Host "백업 파일이 없습니다 — 먼저 backup-db.ps1 을 돌려 주세요"; exit 1 }
$counts = $Dump -replace '\.dump$', '.counts.csv'
$tmp = Join-Path $env:TEMP 'aucs_restore'
$port = 55432
$local = "postgresql://postgres@localhost:$port/aucs"
$log = "$root\logs\restore_test_$(Get-Date -Format 'yyyyMMdd_HHmm').log"
function Say($m) { Write-Host $m; Add-Content -Path $log -Value $m -Encoding UTF8 }
Initialize-PgTools
$sw = [Diagnostics.Stopwatch]::StartNew()
Say "시험할 백업: $Dump"
if (Test-Path $tmp) { & "$pgBin\pg_ctl.exe" -D "$tmp\data" stop -m fast 2>$null | Out-Null; Remove-Item $tmp -Recurse -Force }
New-Item -ItemType Directory -Force -Path $tmp | Out-Null
try {
  & "$pgBin\initdb.exe" -D "$tmp\data" -U postgres -A trust -E UTF8 --locale=C 2>&1 | Out-Null
  & "$pgBin\pg_ctl.exe" -D "$tmp\data" -o "-p $port" -l "$tmp\server.log" -w start | Out-Null
  & "$pgBin\createdb.exe" -h localhost -p $port -U postgres aucs
  # Supabase 에만 있는 것 흉내(로그인 함수·역할·확장 자리)
  $stub = @"
create schema if not exists auth; create schema if not exists extensions;
create or replace function auth.uid() returns uuid language sql as 'select null::uuid';
create or replace function auth.role() returns text language sql as 'select null::text';
create or replace function auth.jwt() returns jsonb language sql as 'select null::jsonb';
do `$`$ begin
  if not exists (select 1 from pg_roles where rolname = 'anon') then create role anon; end if;
  if not exists (select 1 from pg_roles where rolname = 'authenticated') then create role authenticated; end if;
  if not exists (select 1 from pg_roles where rolname = 'service_role') then create role service_role; end if;
end `$`$;
create extension if not exists pgcrypto schema extensions;
create extension if not exists "uuid-ossp" schema extensions;
"@
  & "$pgBin\psql.exe" -d $local -q -c $stub | Out-Null
  # 1) 표 만들기: 좌표 칸은 글자 칸으로 바꿔서
  & "$pgBin\pg_restore.exe" --section=pre-data --no-owner --no-privileges -f "$tmp\pre.sql" $Dump
  $pre = [IO.File]::ReadAllText("$tmp\pre.sql", [Text.Encoding]::UTF8) -replace 'public\.geography\([^)]*\)', 'text' -replace 'public\.geography', 'text'
  [IO.File]::WriteAllText("$tmp\pre.sql", $pre, (New-Object Text.UTF8Encoding $false))
  $e1 = (& "$pgBin\psql.exe" -d $local -q -f "$tmp\pre.sql" 2>&1 | Select-String 'ERROR' | Where-Object { $_ -notmatch 'gist|geography|st_' }).Count
  Say "표 만들기 끝 · 좌표 말고 오류 $e1"
  # 2) 자료 넣기
  Say "자료 넣는 중..."
  $e2 = (& "$pgBin\pg_restore.exe" --section=data --no-owner --no-privileges -j 4 -d $local $Dump 2>&1 | Select-String 'error').Count
  Say "자료 넣기 끝 · 오류 $e2"
  # 3) 색인·제약(좌표 색인은 PostGIS 가 없어 실패해도 됨)
  & "$pgBin\pg_restore.exe" --section=post-data --no-owner --no-privileges -f "$tmp\post.sql" $Dump
  $e3 = (& "$pgBin\psql.exe" -d $local -q -f "$tmp\post.sql" 2>&1 | Select-String 'ERROR' | Where-Object { $_ -notmatch 'gist|geography|st_' }).Count
  Say "색인·제약 끝 · 좌표 말고 오류 $e3"
  # 4) 줄 수 맞춰 보기
  $want = @{}
  if (Test-Path $counts) { Get-Content $counts -Encoding UTF8 | ForEach-Object { $p = $_ -split ','; $want[$p[0]] = [long]$p[1] } }
  $got = @{}
  & "$pgBin\psql.exe" -d $local -At -F ',' -c (Get-CountSql) | ForEach-Object { $p = $_ -split ','; $got[$p[0]] = [long]$p[1] }
  $bad = @()
  foreach ($k in $want.Keys) { if ($got[$k] -ne $want[$k]) { $bad += "$k 백업 $($want[$k]) · 되살림 $($got[$k])" } }
  $total = ($got.Values | Measure-Object -Sum).Sum
  Say ("표 {0}개 · 줄 {1:N0} · 다른 표 {2}개" -f $got.Count, $total, $bad.Count)
  $bad | ForEach-Object { Say "  다름: $_" }
  # 회원 백업 파일이 읽히는지
  $auth = $Dump -replace '\.dump$', '.auth.dump'
  if (Test-Path $auth) {
    $ok = (& "$pgBin\pg_restore.exe" --list $auth 2>&1 | Select-String 'TABLE DATA auth users').Count
    Say ("회원 백업 읽힘: " + ($(if ($ok) { '예' } else { '아니오' })))
  }
  $pass = ($bad.Count -eq 0 -and $e1 -eq 0 -and $e2 -eq 0 -and $e3 -eq 0 -and $want.Count -gt 0)
  Say ("결과: " + ($(if ($pass) { '통과' } else { '확인 필요' })) + " · $([math]::Round($sw.Elapsed.TotalMinutes, 1))분 · 로그 $log")
  try {
    $url = Get-DbUrl
    $st = if ($pass) { 'ok' } else { 'failed' }
    & "$pgBin\psql.exe" -d $url -q -c "insert into ops.jobs (job_id, name_ko) values ('restore_test', 'DB 복구 시험') on conflict do nothing; insert into ops.job_runs (job_id, finished_at, status, item_count, message) values ('restore_test', now(), '$st', $($got.Count), '다른 표 $($bad.Count) · 오류 $($e1 + $e2 + $e3)')" | Out-Null
  } catch { Say "관리자 화면 기록은 못 남김: $_" }
} finally {
  & "$pgBin\pg_ctl.exe" -D "$tmp\data" stop -m fast 2>$null | Out-Null
  Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
}
