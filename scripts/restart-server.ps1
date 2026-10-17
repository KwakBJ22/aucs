# 옥스 서버 다시 켜기 (새 꾸러미 설치가 필요할 때 등). 창 없이 다시 켜집니다.
foreach ($n in '서버_API', '서버_웹') { Stop-ScheduledTask -TaskPath '\Aucs\' -TaskName $n -ErrorAction SilentlyContinue }
foreach ($port in 3000, 3001, 8100) {
  Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
    ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
}
Start-Sleep -Seconds 2
foreach ($n in '서버_API', '서버_웹') { Start-ScheduledTask -TaskPath '\Aucs\' -TaskName $n }
Write-Host "다시 켰습니다. 1분쯤 뒤 http://localhost:3000 을 열어 보세요."
