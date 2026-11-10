@echo off
chcp 65001 >nul
rem Aucs deploy: pull from GitHub, promote only when every check passes (no skip path)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\deploy.ps1"
echo.
pause
