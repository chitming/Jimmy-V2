@echo off
setlocal
cd /d "%~dp0"

REM Prefer running the PowerShell installer with Bypass so double-click works.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Install-TDR.ps1" -StartAfterInstall
if errorlevel 1 (
  echo.
  echo Install failed. If PowerShell blocked the script, right-click Install-TDR.ps1
  echo and choose "Run with PowerShell", or open PowerShell in this folder and run:
  echo   Set-ExecutionPolicy -Scope Process Bypass
  echo   .\Install-TDR.ps1
  pause
  exit /b 1
)
echo.
pause
