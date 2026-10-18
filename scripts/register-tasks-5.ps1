# 아침 묶음으로 바꾸기 (10/18 대표님): 매일 07:00 한 작업 안에서 매각결과 → 물건 → 분석 → 서류 → 분석 → 알림.
# PC가 07:00에 꺼져 있으면 켜지는 순간 시작(StartWhenAvailable). 입찰일 아침 알림(07:30)은 그대로.
# 예전 작업 5개는 지우지 않고 끔. 다시 켜기: Enable-ScheduledTask -TaskPath '\Aucs\' -TaskName '물건'
$run = Join-Path $PSScriptRoot 'run-job.ps1'
$tr = "powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$run`" daily"
schtasks /Create /TN "\Aucs\아침_묶음" /SC DAILY /ST 07:00 /TR $tr /F | Out-Null
$s = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 5)
Set-ScheduledTask -TaskPath '\Aucs\' -TaskName '아침_묶음' -Settings $s | Out-Null
Write-Host "등록: \Aucs\아침_묶음 — 매일 07:00 (꺼져 있었으면 켜질 때)"
foreach ($t in '매각결과', '물건', '서류보관', '분석', '알림') {
  Disable-ScheduledTask -TaskPath '\Aucs\' -TaskName $t -ErrorAction SilentlyContinue | Out-Null
  Write-Host "끔: \Aucs\$t (지우지 않음)"
}
Get-ScheduledTask -TaskPath '\Aucs\' | ForEach-Object { '{0} · {1}' -f $_.TaskName, $_.State }
