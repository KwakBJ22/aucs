# 옥스 DB 백업 — 우리 표(core·analysis·app·ops·ref·raw) + 회원(auth.users)을 D:\Auction\backup 에 받아 둠. 최근 8개만 남김.
# 실행: powershell -ExecutionPolicy Bypass -File D:\Auction\auction-platform\scripts\backup-db.ps1
# 작업 스케줄러: 매주 일요일 12:00(register-tasks.ps1). 받는 데 10~30분(서류 원문 raw 가 5GB 넘음).
# 되살려지는지는 restore-test.ps1 로 따로 시험.
$ErrorActionPreference = 'Continue'  # 바깥 프로그램이 안내 글을 오류 칸에 써도 멈추지 않게(끝 코드로 판단)
. "$PSScriptRoot\pgtools.ps1"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PGCLIENTENCODING = 'UTF8'
$dir = Join-Path (Split-Path -Parent $root) 'backup'
New-Item -ItemType Directory -Force -Path $dir, "$root\logs" | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd_HHmm'
$log = "$root\logs\backup_$stamp.log"
try {
  Initialize-PgTools
  $url = Get-DbUrl
  $out = "$dir\aucs_$stamp.dump"
  $sw = [Diagnostics.Stopwatch]::StartNew()
  Write-Host "줄 수 적는 중..." | Tee-Object -FilePath $log -Append
  & "$pgBin\psql.exe" -d $url -At -F ',' -c (Get-CountSql) -o "$dir\aucs_$stamp.counts.csv"
  if ($LASTEXITCODE -ne 0) { throw "줄 수 읽기 실패($LASTEXITCODE)" }
  Write-Host "우리 표 받는 중 → $out" | Tee-Object -FilePath $log -Append
  $args1 = @('-d', $url, '-Fc', '-Z', '6', '--no-owner', '--no-privileges', '-f', $out) + ($schemas | ForEach-Object { '-n', $_ })
  & "$pgBin\pg_dump.exe" @args1 2>&1 | Tee-Object -FilePath $log -Append
  if ($LASTEXITCODE -ne 0) { throw "pg_dump 실패($LASTEXITCODE)" }
  Write-Host "회원(auth.users) 받는 중" | Tee-Object -FilePath $log -Append
  & "$pgBin\pg_dump.exe" -d $url -Fc --data-only --no-owner --no-privileges -t auth.users -f "$dir\aucs_$stamp.auth.dump" 2>&1 | Tee-Object -FilePath $log -Append
  if ($LASTEXITCODE -ne 0) { throw "회원 받기 실패($LASTEXITCODE)" }
  # 오래된 것 지우기(최근 8개 = 두 달)
  Get-ChildItem $dir -Filter 'aucs_*.dump' | Where-Object { $_.Name -notlike '*.auth.dump' } | Sort-Object Name -Descending | Select-Object -Skip 8 | ForEach-Object {
    $base = $_.FullName -replace '\.dump$', ''
    Remove-Item "$base.dump", "$base.auth.dump", "$base.counts.csv" -ErrorAction SilentlyContinue
  }
  $mb = [math]::Round((Get-Item $out).Length / 1MB)
  $msg = "백업 끝: $out ($mb MB, $([math]::Round($sw.Elapsed.TotalMinutes, 1))분)"
  Write-Host $msg | Tee-Object -FilePath $log -Append
  $rc = Invoke-PgSql $url "insert into ops.jobs (job_id, name_ko) values ('backup', 'DB 백업') on conflict do nothing; insert into ops.job_runs (job_id, finished_at, status, item_count, message) values ('backup', now(), 'ok', $mb, '$mb MB · aucs_$stamp');"
  if ($rc -ne 0) { Write-Host "관리자 화면 기록은 못 남김(백업 파일은 정상)" | Tee-Object -FilePath $log -Append }
} catch {
  "멈춤: $_" | Tee-Object -FilePath $log -Append
  Add-Type -AssemblyName System.Windows.Forms
  [System.Windows.Forms.MessageBox]::Show("옥스 DB 백업이 멈췄습니다.`n`n$_`n`n로그: $log", '옥스 — 백업 확인') | Out-Null
  exit 1
}
