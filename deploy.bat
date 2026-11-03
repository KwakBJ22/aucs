@echo off
chcp 65001 >nul
rem 옥스 배포: 검사가 모두 초록일 때만 올라갑니다(건너뛰기 없음)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\deploy.ps1"
echo.
pause
