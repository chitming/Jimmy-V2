TDR — Technical Drawing Reader (Windows)

Docker (recommended)
--------------------
If you have Docker Desktop, clone and run as container "jimmy-v2":

  git clone -b cursor/sheetsense-layout-mvp-f8ab https://github.com/chitming/Jimmy-V2.git %USERPROFILE%\Jimmy-V2
  cd %USERPROFILE%\Jimmy-V2
  powershell -ExecutionPolicy Bypass -File .\scripts\Clone-JimmyV2-Docker.ps1 -SkipClone -Profile slim

Or:
  docker compose --profile slim up --build -d
  open http://localhost:8000/

Native Windows installer
------------------------
1. Unzip TDR-Windows-Setup.zip to a folder (e.g. Downloads\TDR-Windows)
2. Double-click setup.bat
   Or right-click Install-TDR.ps1 → Run with PowerShell
3. Wait for Python packages to install (several minutes the first time)
4. Use the Desktop shortcut "TDR" to start the app
5. Browser opens at http://127.0.0.1:8000/

Requirements (native installer)
-------------------------------
- Windows 10/11 (64-bit)
- Python 3.11+ (installer can install via winget)
- Git (needed for one optional dependency; installer can install via winget)
- Tesseract OCR (installer tries winget: UB-Mannheim.TesseractOCR)

If winget is unavailable, install manually:
- Python: https://www.python.org/downloads/  (enable "Add python.exe to PATH")
- Tesseract: https://github.com/UB-Mannheim/tesseract/wiki

Start / Stop (native)
---------------------
- Start: Desktop "TDR" shortcut, or Start-TDR.cmd in the install folder
- Stop:  Stop-TDR.cmd

Default install location
------------------------
%LOCALAPPDATA%\Programs\TDR

Uninstall
---------
Run Uninstall-TDR.ps1 from the install folder, or from this package after install.
