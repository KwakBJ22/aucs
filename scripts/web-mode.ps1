# 화면 서버 방식 바꾸기
#   빠른 보기:  powershell -ExecutionPolicy Bypass -File D:\Auction\auction-platform\scripts\web-mode.ps1 fast
#   개발 방식:  powershell -ExecutionPolicy Bypass -File D:\Auction\auction-platform\scripts\web-mode.ps1 dev
# fast = 미리 만들어 실제 서비스처럼(빠름, 코드 고친 뒤엔 fast 를 다시 실행해야 반영)
# dev  = 고치면 바로 반영(처음 여는 화면은 몇 초 걸림)
param([ValidateSet('fast', 'dev')][string]$Mode = 'fast')
$root = Split-Path -Parent $PSScriptRoot
Set-Content -Path "$root\scripts\web-mode.txt" -Value $Mode -Encoding ascii
Stop-ScheduledTask -TaskPath '\Aucs\' -TaskName '서버_웹' -ErrorAction SilentlyContinue
Get-NetTCPConnection -LocalPort 3000 -State Listen -ErrorAction SilentlyContinue |
  ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 2
Start-ScheduledTask -TaskPath '\Aucs\' -TaskName '서버_웹'
if ($Mode -eq 'fast') {
  Write-Host "빠른 보기로 바꿨습니다. 만드는 데 1~2분 걸립니다. 그 뒤 http://localhost:3000 을 여세요."
  Write-Host "진행 기록: $root\logs\server_web.log"
} else {
  Write-Host "개발 방식으로 바꿨습니다. 30초쯤 뒤 http://localhost:3000 을 여세요."
}
