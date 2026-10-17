# 옥스 매일 작업 등록 + 지금 시스템의 법원 수집 3개 끄기 (10/17 대표님 결정: 새 것으로 교체)
# 다시 켜기: Enable-ScheduledTask -TaskPath '\Auction\' -TaskName '경매물건_주간' (매각결과_주간·서류보관_매일 도 같음)
$run = Join-Path $PSScriptRoot 'run-job.ps1'
function Add-Daily($name, $job, $time, $hours) {
  $tr = "powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$run`" $job"
  schtasks /Create /TN "\Aucs\$name" /SC DAILY /ST $time /TR $tr /F | Out-Null
  $s = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours $hours)
  Set-ScheduledTask -TaskPath '\Aucs\' -TaskName $name -Settings $s | Out-Null
  Write-Host "등록: \Aucs\$name — 매일 $time"
}
Add-Daily '매각결과' 'results' '10:00' 1
Add-Daily '물건' 'items' '11:30' 2
Add-Daily '서류보관' 'docs' '13:30' 2
Add-Daily '분석' 'analyze' '15:30' 1
foreach ($t in '경매물건_주간', '매각결과_주간', '서류보관_매일') {
  Disable-ScheduledTask -TaskPath '\Auction\' -TaskName $t -ErrorAction SilentlyContinue | Out-Null
  Write-Host "끔: \Auction\$t (지우지 않음)"
}
Write-Host "그대로 둠: 실거래가_월간 · 관심물건_매일 · 정비사업_분기 · 화면서버"
Get-ScheduledTask -TaskPath '\Aucs\' | ForEach-Object { '{0} · {1}' -f $_.TaskName, $_.State }
