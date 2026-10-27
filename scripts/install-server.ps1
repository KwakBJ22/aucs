# 옥스 서버(API 8100·웹 3000)를 항상 켜 두기. 한 번만 실행하면 됩니다.
# 컴퓨터에 로그인하면 창 없이 저절로 켜지고, 꺼지면 다시 켜집니다. 기록: logs\server_api.log, logs\server_web.log
# 멈추기: Stop-ScheduledTask -TaskPath '\Aucs\' -TaskName '서버_API' (서버_웹 도 같음) / 지우기: Unregister-ScheduledTask 같은 이름
$serve = Join-Path $PSScriptRoot 'serve.ps1'
# 지금 떠 있는 창(예전 dev.ps1)과 겹치지 않게 3000·8100 을 쓰는 프로그램을 먼저 끔
foreach ($port in 3000, 8100) {
  Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
    ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
}
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
  -ExecutionTimeLimit (New-TimeSpan -Seconds 0) -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -MultipleInstances IgnoreNew
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
foreach ($t in @(@('서버_API', 'api'), @('서버_웹', 'web'))) {
  $action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$serve`" $($t[1])"
  Register-ScheduledTask -TaskPath '\Aucs\' -TaskName $t[0] -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
  Start-ScheduledTask -TaskPath '\Aucs\' -TaskName $t[0]
  Write-Host "등록하고 켰습니다: \Aucs\$($t[0])"
}
Write-Host "30초쯤 뒤 http://localhost:3000 을 열어 보세요. 이제 PowerShell 창은 닫으셔도 됩니다."
