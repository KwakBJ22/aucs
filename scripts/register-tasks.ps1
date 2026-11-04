# 옥스 작업 스케줄러 등록 — 지금 쓰는 작업 전부 (한 번 돌리면 같은 상태가 됨, 여러 번 돌려도 됨)
# 10/28 정리: 예전 register-tasks-2~5 를 이 파일 하나로 합침.
#   켜 둠: 아침_묶음 매일 07:00(매각결과→물건→건축물대장→공매→분석→알림) · 법원_매시 매시 10분(11/4) · 입찰일_아침 매일 07:30
#          관심_바로_준비 09:05~21:05 매시(10/29, 관심 담은 뒤 서류·건축물대장·분석)
#          관리자_요청 5분마다(11/2) · DB_백업 매주 일요일 12:00(10/29, backup-db.ps1) · 실거래 매월 2일 10:00 · 정비사업 1·4·7·10월 3일 11:00
#   꺼 둠(지우지 않음): \Aucs\ 매각결과·물건·서류보관·분석·알림(아침 묶음으로 바뀜, 10/18)
#                      \Auction\ 경매레이더 수집 5개(옥스로 넘김, 10/17)
#   다시 켜기 예: Enable-ScheduledTask -TaskPath '\Aucs\' -TaskName '물건'
# 모든 작업: PC가 그 시각에 꺼져 있었으면 켜질 때 시작, 배터리로 돌 때도 시작·도중에 멈추지 않음(10/22 원인)
$run = Join-Path $PSScriptRoot 'run-job.ps1'
# 창이 떴다 사라지지 않게 hidden.vbs 로 띄움(11/2)
$vbs = Join-Path $PSScriptRoot 'hidden.vbs'
$tr = "wscript.exe `"$vbs`" `"$run`""
function Set-Opts($name, $hours) {
  $s = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours $hours)
  Set-ScheduledTask -TaskPath '\Aucs\' -TaskName $name -Settings $s | Out-Null
}

schtasks /Create /TN "\Aucs\아침_묶음" /SC DAILY /ST 07:00 /TR "$tr daily" /F | Out-Null; Set-Opts '아침_묶음' 5
Write-Host "등록: \Aucs\아침_묶음 — 매일 07:00"
schtasks /Create /TN "\Aucs\입찰일_아침" /SC DAILY /ST 07:30 /TR "$tr morning" /F | Out-Null; Set-Opts '입찰일_아침' 1
Write-Host "등록: \Aucs\입찰일_아침 — 매일 07:30"
schtasks /Create /TN "\Aucs\관심_바로_준비" /SC DAILY /ST 09:05 /RI 60 /DU 12:00 /TR "$tr watched" /F | Out-Null; Set-Opts '관심_바로_준비' 1
Write-Host "등록: \Aucs\관심_바로_준비 — 09:05~21:05 매시(관심 담은 뒤 건축물대장·분석, 서류는 법원_매시)"
# 11/4 저녁: 법원 사건 서류·사진·다음 회차·감정평가서는 매시 나눠 받음(하루 한도 ÷ 18시간). 매시 10분, 하루 종일 —
#   밤(01~06시)에는 작업이 스스로 쉼. PC 가 꺼져 있다 켜지면 바로 한 번 돌고(StartWhenAvailable), 앞 차례가 돌고 있으면 건너뜀.
schtasks /Create /TN "\Aucs\법원_매시" /SC HOURLY /MO 1 /ST 06:10 /TR "$tr court_hourly" /F | Out-Null; Set-Opts '법원_매시' 2
Write-Host "등록: \Aucs\법원_매시 — 매시 10분(관심 서류 → 추천 사진 → 다음 회차 → 서류 보관 → 감정평가서 원본 → 분석)"
$rq = Join-Path $PSScriptRoot 'run-requests.ps1'
schtasks /Create /TN "\Aucs\관리자_요청" /SC MINUTE /MO 5 /TR "wscript.exe `"$vbs`" `"$rq`"" /F | Out-Null; Set-Opts '관리자_요청' 6
Write-Host "등록: \Aucs\관리자_요청 — 5분마다(관리자 화면 「다시 돌리기 요청」)"
$bk = Join-Path $PSScriptRoot 'backup-db.ps1'
schtasks /Create /TN "\Aucs\DB_백업" /SC WEEKLY /D SUN /ST 12:00 /TR "wscript.exe `"$vbs`" `"$bk`"" /F | Out-Null; Set-Opts 'DB_백업' 2
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
