# 옥스 예약 작업이 무엇을 실행하는지 + 마지막·다음 실행 시각(11/2 창 깜빡임 확인용)
Get-ScheduledTask -TaskPath '\Aucs\' | Where-Object State -ne 'Disabled' | ForEach-Object {
  $i = $_ | Get-ScheduledTaskInfo
  '{0,-10} {1,-14} 마지막 {2:HH:mm} 다음 {3:HH:mm}  {4}' -f $_.TaskName, $_.Actions[0].Execute, $i.LastRunTime, $i.NextRunTime, (($_.Actions[0].Arguments) -replace '.*\\scripts\\', '')
}
Write-Host ''
Write-Host '지금 떠 있는 PowerShell·python 창:'
Get-Process powershell, pwsh, python, uv, conhost -ErrorAction SilentlyContinue | Where-Object MainWindowTitle | Format-Table Id, ProcessName, StartTime, MainWindowTitle -AutoSize
