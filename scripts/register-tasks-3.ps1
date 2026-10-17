# 알림 작업만 추가 등록 (분석 뒤 16:30)
$run = Join-Path $PSScriptRoot 'run-job.ps1'
function Add-Daily($name, $job, $time, $hours) {
  $tr = "powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$run`" $job"
  schtasks /Create /TN "\Aucs\$name" /SC DAILY /ST $time /TR $tr /F | Out-Null
  $s = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours $hours)
  Set-ScheduledTask -TaskPath '\Aucs\' -TaskName $name -Settings $s | Out-Null
  Write-Host "등록: \Aucs\$name — 매일 $time"
}
Add-Daily '알림' 'notify' '16:30' 1
