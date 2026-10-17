# 옥스 실거래(매달)·정비사업(분기) 등록 + 경매레이더 실거래가_월간·정비사업_분기 끄기 (10/17 대표님 결정)
# 다시 켜기: Enable-ScheduledTask -TaskPath '\Auction\' -TaskName '실거래가_월간' (정비사업_분기 도 같음)
$run = Join-Path $PSScriptRoot 'run-job.ps1'
function Set-Opts($name, $hours) {
  $s = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours $hours)
  Set-ScheduledTask -TaskPath '\Aucs\' -TaskName $name -Settings $s | Out-Null
}
$tr = "powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$run`""
schtasks /Create /TN "\Aucs\실거래" /SC MONTHLY /D 2 /ST 10:00 /TR "$tr trades" /F | Out-Null; Set-Opts '실거래' 3
Write-Host "등록: \Aucs\실거래 — 매월 2일 10:00"
schtasks /Create /TN "\Aucs\정비사업" /SC MONTHLY /M JAN,APR,JUL,OCT /D 3 /ST 11:00 /TR "$tr redev" /F | Out-Null; Set-Opts '정비사업' 1
Write-Host "등록: \Aucs\정비사업 — 1·4·7·10월 3일 11:00"
foreach ($t in '실거래가_월간', '정비사업_분기') {
  Disable-ScheduledTask -TaskPath '\Auction\' -TaskName $t -ErrorAction SilentlyContinue | Out-Null
  Write-Host "끔: \Auction\$t (지우지 않음)"
}
Get-ScheduledTask -TaskPath '\Aucs\' | ForEach-Object { '{0} · {1}' -f $_.TaskName, $_.State }
