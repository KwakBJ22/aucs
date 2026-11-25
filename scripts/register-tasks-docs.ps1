# 옥스 2번 PC(서류 보관 담당, 11/26) 작업 스케줄러 등록 — 법원_매시 하나만. 1번 PC 에서는 돌리지 말 것(register-tasks.ps1 을 씀).
# .env 에 AUCS_ROLE=docs 가 있어야 서류 보관만 돎(없으면 1번 PC 처럼 다 돌아 겹침).
$root = Split-Path -Parent $PSScriptRoot
if (-not (Select-String -Path "$root\.env" -Pattern '^AUCS_ROLE=docs' -Quiet)) { Write-Host '.env 에 AUCS_ROLE=docs 가 없습니다 — 먼저 넣으세요'; exit 1 }
$run = Join-Path $PSScriptRoot 'run-job.ps1'
$vbs = Join-Path $PSScriptRoot 'hidden.vbs'
$tr = "wscript.exe `"$vbs`" `"$run`""
schtasks /Create /TN "\Aucs\법원_매시" /SC HOURLY /MO 1 /ST 06:10 /TR "$tr court_hourly" /F | Out-Null
$s = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 2)
Set-ScheduledTask -TaskPath '\Aucs\' -TaskName '법원_매시' -Settings $s | Out-Null
# 이 PC 의 하루 법원 한도 — 1번 PC 와 따로(다른 인터넷). 처음 8,000번, 3일 무사하면 20%씩(polite.py)
New-Item -ItemType Directory -Force -Path "$root\logs" | Out-Null
if (-not (Test-Path "$root\logs\court_budget.json")) { '{"cap": 8000}' | Set-Content -Encoding ascii "$root\logs\court_budget.json" }
Write-Host '등록: \Aucs\법원_매시 — 매시 10분(2번 PC: 서류 보관 · 14시 뒤 전국 보관)'
