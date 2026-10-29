# 옥스 작업 스케줄러 등록 — 지금 쓰는 작업 전부 (한 번 돌리면 같은 상태가 됨, 여러 번 돌려도 됨)
# 10/28 정리: 예전 register-tasks-2~5 를 이 파일 하나로 합침.
#   켜 둠: 아침_묶음 매일 07:00(매각결과→물건→분석→서류→분석→알림) · 입찰일_아침 매일 07:30
#          관심_바로_준비 09:05~21:05 매시(10/29, 관심 담은 뒤 서류·건축물대장·분석)
#          DB_백업 매주 일요일 12:00(10/29, backup-db.ps1) · 실거래 매월 2일 10:00 · 정비사업 1·4·7·10월 3일 11:00
#   꺼 둠(지우지 않음): \Aucs\ 매각결과·물건·서류보관·분석·알림(아침 묶음으로 바뀜, 10/18)
#                      \Auction\ 경매레이더 수집 5개(옥스로 넘김, 10/17)
#   다시 켜기 예: Enable-ScheduledTask -TaskPath '\Aucs\' -TaskName '물건'
# 모든 작업: PC가 그 시각에 꺼져 있었으면 켜질 때 시작, 배터리로 돌 때도 시작·도중에 멈추지 않음(10/22 원인)
$run = Join-Path $PSScriptRoot 'run-job.ps1'
$tr = "powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$run`""
function Set-Opts($name, $hours) {
  $s = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours $hours)
  Set-ScheduledTask -TaskPath '\Aucs\' -TaskName $name -Settings $s | Out-Null
}

schtasks /Create /TN "\Aucs\아침_묶음" /SC DAILY /ST 07:00 /TR "$tr daily" /F | Out-Null; Set-Opts '아침_묶음' 5
Write-Host "등록: \Aucs\아침_묶음 — 매일 07:00"
schtasks /Create /TN "\Aucs\입찰일_아침" /SC DAILY /ST 07:30 /TR "$tr morning" /F | Out-Null; Set-Opts '입찰일_아침' 1
Write-Host "등록: \Aucs\입찰일_아침 — 매일 07:30"
schtasks /Create /TN "\Aucs\관심_바로_준비" /SC DAILY /ST 09:05 /RI 60 /DU 12:00 /TR "$tr watched" /F | Out-Null; Set-Opts '관심_바로_준비' 1
Write-Host "등록: \Aucs\관심_바로_준비 — 09:05~21:05 매시(관심 담은 뒤 서류·건축물대장)"
$bk = Join-Path $PSScriptRoot 'backup-db.ps1'
schtasks /Create /TN "\Aucs\DB_백업" /SC WEEKLY /D SUN /ST 12:00 /TR "powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$bk`"" /F | Out-Null; Set-Opts 'DB_백업' 2
Write-Host "등록: \Aucs\DB_백업 — 매주 일요일 12:00(D:\Auction\backup, 최근 8개)"
schtasks /Create /TN "\Aucs\실거래" /SC MONTHLY /D 2 /ST 10:00 /TR "$tr trades" /F | Out-Null; Set-Opts '실거래' 3
Write-Host "등록: \Aucs\실거래 — 매월 2일 10:00"
schtasks /Create /TN "\Aucs\정비사업" /SC MONTHLY /M JAN,APR,JUL,OCT /D 3 /ST 11:00 /TR "$tr redev" /F | Out-Null; Set-Opts '정비사업' 1
Write-Host "등록: \Aucs\정비사업 — 1·4·7·10월 3일 11:00"

foreach ($t in '매각결과', '물건', '서류보관', '분석', '알림') {
  Disable-ScheduledTask -TaskPath '\Aucs\' -TaskName $t -ErrorAction SilentlyContinue | Out-Null
}
foreach ($t in '경매물건_주간', '매각결과_주간', '서류보관_매일', '실거래가_월간', '정비사업_분기') {
  Disable-ScheduledTask -TaskPath '\Auction\' -TaskName $t -ErrorAction SilentlyContinue | Out-Null
}
Write-Host "꺼 둠: 예전 작업(지우지 않음)"
Get-ScheduledTask -TaskPath '\Aucs\' | ForEach-Object { '{0} · {1}' -f $_.TaskName, $_.State }
