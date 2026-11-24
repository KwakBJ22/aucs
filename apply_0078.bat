@echo off
chcp 65001 >nul
rem 11/24 대표님 외부 — Claude 가 이주 0078 을 적용하려고 만든 한 번용 파일(파일 탐색기에서 두 번 눌러 실행)
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\apply-sql.ps1 db\migrations\0078_points_registry_1200.sql
echo.
pause
