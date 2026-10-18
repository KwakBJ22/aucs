# 입찰일 아침 알림 등록 (매일 07:30)
$run = Join-Path $PSScriptRoot 'run-job.ps1'
$tr = "powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$run`" morning"
schtasks /Create /TN "\Aucs\입찰일_아침" /SC DAILY /ST 07:30 /TR $tr /F | Out-Null
$s = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 1)
Set-ScheduledTask -TaskPath '\Aucs\' -TaskName '입찰일_아침' -Settings $s | Out-Null
Write-Host "등록: \Aucs\입찰일_아침 — 매일 07:30"
