# 옥스 DB 백업·복구 시험이 같이 쓰는 것: PostgreSQL 17 도구(pg_dump·pg_restore·psql) 준비, .env 의 DATABASE_URL 읽기
$root = Split-Path -Parent $PSScriptRoot
$pgBin = "$root\tools\pgsql\bin"
# EDB 「PostgreSQL 17 Windows x86-64 binaries」 zip(설치 없이 압축만 풂, 약 300MB). 주소가 바뀌면 아래 줄만 고치거나
# https://www.enterprisedb.com/download-postgresql-binaries 에서 받은 zip 을 tools\pgsql.zip 으로 두면 됨
$pgZipUrl = 'https://sbp.enterprisedb.com/getfile.jsp?fileid=1260616'
$schemas = @('core', 'analysis', 'app', 'ops', 'ref', 'raw')  # public 은 PostGIS 것만 있어 뺌

function Initialize-PgTools {
  if (Test-Path "$pgBin\pg_dump.exe") { return }
  $zip = "$root\tools\pgsql.zip"
  New-Item -ItemType Directory -Force -Path "$root\tools" | Out-Null
  if (-not (Test-Path $zip)) {
    Write-Host "PostgreSQL 17 도구 받는 중(처음 한 번, 약 300MB)..."
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    $ProgressPreference = 'SilentlyContinue'
    Invoke-WebRequest -Uri $pgZipUrl -OutFile $zip -UseBasicParsing
  }
  Expand-Archive -Path $zip -DestinationPath "$root\tools" -Force
  if (-not (Test-Path "$pgBin\pg_dump.exe")) { throw "tools\pgsql\bin\pg_dump.exe 가 없습니다 — zip 을 확인해 주세요" }
}

function Get-DbUrl {
  $line = Get-Content "$root\.env" -Encoding UTF8 | Where-Object { $_ -match '^\s*DATABASE_URL\s*=' } | Select-Object -First 1
  if (-not $line) { throw '.env 에 DATABASE_URL 이 없습니다' }
  return ($line -replace '^\s*DATABASE_URL\s*=\s*', '').Trim().Trim('"').Trim("'")
}

# 표마다 정확한 줄 수(백업 때 적어 두고, 복구 시험 때 맞춰 봄)
function Get-CountSql {
  $list = ($schemas | ForEach-Object { "'$_'" }) -join ','
  return "select table_schema||'.'||table_name, (xpath('/row/c/text()', query_to_xml(format('select count(*) as c from %I.%I', table_schema, table_name), false, true, '')))[1]::text from information_schema.tables where table_schema in ($list) and table_type = 'BASE TABLE' order by 1"
}

# 한글이 든 SQL 을 psql 에 넘길 때: 명령 줄(-c)로 넘기면 Windows 가 CP949 로 바꿔 「invalid byte sequence for encoding UTF8」(11/2).
# UTF-8 파일로 써서 -f 로 넘김.
function Invoke-PgSql([string]$url, [string]$sql) {
  $f = Join-Path $env:TEMP ("aucs_sql_{0}.sql" -f [guid]::NewGuid().ToString('N'))
  [IO.File]::WriteAllText($f, $sql, (New-Object Text.UTF8Encoding $false))
  try { & "$pgBin\psql.exe" -d $url -q -v ON_ERROR_STOP=1 -f $f | Out-Null; return $LASTEXITCODE } finally { Remove-Item $f -ErrorAction SilentlyContinue }
}

# pg_ctl start 는 출력을 | Out-Null 로 받으면 띄운 DB 서버가 그 통로를 계속 잡고 있어 PowerShell 이 끝없이 기다림(11/1 복구 시험 멈춤).
# 출력 통로 없이 띄우고 pg_ctl 만 기다림.
function Invoke-PgCtl([string[]]$argv) {
  $p = Start-Process -FilePath "$pgBin\pg_ctl.exe" -ArgumentList $argv -NoNewWindow -PassThru
  $null = $p.Handle  # 이걸 잡아 둬야 끝난 뒤 ExitCode 가 비지 않음
  $p.WaitForExit()
  return $p.ExitCode
}
