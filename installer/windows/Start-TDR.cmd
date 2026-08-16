@echo off
setlocal
cd /d "%~dp0backend"
if not exist ".venv\Scripts\python.exe" (
  echo TDR is not installed correctly. Run setup.bat / Install-TDR.ps1 first.
  pause
  exit /b 1
)

REM Stop any previous instance on port 8000
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8000" ^| findstr "LISTENING"') do (
  taskkill /PID %%p /F >nul 2>&1
)

echo Starting TDR on http://127.0.0.1:8000 ...
start "TDR" /MIN ".venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000

REM Wait for the API to come up, then open the browser
powershell -NoProfile -Command ^
  "$ok=$false; for($i=0;$i -lt 60;$i++){ try { $r=Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/api/stats -TimeoutSec 2; if($r.StatusCode -eq 200){$ok=$true; break} } catch {} ; Start-Sleep -Seconds 1 }; if(-not $ok){ exit 1 }"

if errorlevel 1 (
  echo TDR did not become ready in time. Check the TDR console window for errors.
  pause
  exit /b 1
)

start "" "http://127.0.0.1:8000/"
echo TDR is running. Close the minimized "TDR" window or run Stop-TDR.cmd to stop.
endlocal
