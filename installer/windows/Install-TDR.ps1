#Requires -Version 5.1
<#
.SYNOPSIS
  Install TDR (Technical Drawing Reader) on Windows.

.DESCRIPTION
  Copies the packaged app into %LOCALAPPDATA%\Programs\TDR, creates a Python
  virtualenv, installs dependencies, optionally installs Tesseract/Git via winget,
  and creates Start Menu + Desktop shortcuts.

.EXAMPLE
  Right-click Install-TDR.ps1 → Run with PowerShell
  Or: powershell -ExecutionPolicy Bypass -File .\Install-TDR.ps1
#>
[CmdletBinding()]
param(
  [string]$InstallDir = "$env:LOCALAPPDATA\Programs\TDR",
  [switch]$SkipWinget,
  [switch]$StartAfterInstall
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$BundleApp = Join-Path $Root "app"

function Write-Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Write-Ok($msg) { Write-Host "    $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "    $msg" -ForegroundColor Yellow }

Write-Host "TDR Windows installer" -ForegroundColor White
Write-Host "Install to: $InstallDir"

if (-not (Test-Path (Join-Path $BundleApp "backend\app\main.py"))) {
  throw "Package incomplete: expected app\backend under $Root. Re-download TDR-Windows-Setup.zip."
}

function Test-Command($Name) {
  return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

function Ensure-WingetPackage {
  param([string]$Id, [string]$DisplayName)
  if ($SkipWinget) { return $false }
  if (-not (Test-Command "winget")) {
    Write-Warn "winget not available; skip auto-install of $DisplayName"
    return $false
  }
  Write-Step "Checking $DisplayName ($Id) via winget"
  $list = winget list --id $Id -e 2>$null
  if ($LASTEXITCODE -eq 0 -and "$list" -match [regex]::Escape($Id)) {
    Write-Ok "$DisplayName already installed"
    return $true
  }
  Write-Host "    Installing $DisplayName…"
  winget install --id $Id -e --accept-source-agreements --accept-package-agreements
  if ($LASTEXITCODE -ne 0) {
    Write-Warn "Could not install $DisplayName automatically. Install it manually if needed."
    return $false
  }
  Write-Ok "$DisplayName installed"
  return $true
}

# --- Prerequisites ---
Ensure-WingetPackage -Id "Python.Python.3.12" -DisplayName "Python 3.12" | Out-Null
Ensure-WingetPackage -Id "Git.Git" -DisplayName "Git" | Out-Null
Ensure-WingetPackage -Id "UB-Mannheim.TesseractOCR" -DisplayName "Tesseract OCR" | Out-Null

# Refresh PATH for this session (winget installs)
$env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
            [System.Environment]::GetEnvironmentVariable("Path", "User")

$Python = $null
$PythonArgs = @()
foreach ($cand in @("py", "python", "python3")) {
  if (Test-Command $cand) {
    try {
      if ($cand -eq "py") {
        $ver = & $cand -3 -c "import sys; print(f'{sys.version_info[0]}.{sys.version_info[1]}')" 2>$null
        if ($ver -match '^3\.(1[1-9]|[2-9]\d)') {
          $Python = "py"
          $PythonArgs = @("-3")
          break
        }
      } else {
        $ver = & $cand -c "import sys; print(f'{sys.version_info[0]}.{sys.version_info[1]}')" 2>$null
        if ($ver -match '^3\.(1[1-9]|[2-9]\d)') {
          $Python = $cand
          $PythonArgs = @()
          break
        }
      }
    } catch { }
  }
}
if (-not $Python) {
  throw "Python 3.11+ not found. Install from https://www.python.org/downloads/ (check 'Add to PATH'), then re-run this installer."
}
Write-Step "Using Python: $Python $($PythonArgs -join ' ')"
& $Python @PythonArgs --version

# --- Copy files ---
Write-Step "Copying application files"
New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
# Preserve existing data/ if reinstalling
$dataBackup = $null
$existingData = Join-Path $InstallDir "backend\data"
if (Test-Path $existingData) {
  $dataBackup = Join-Path $env:TEMP ("tdr-data-backup-" + [guid]::NewGuid().ToString("N"))
  Write-Warn "Backing up existing data to $dataBackup"
  Copy-Item -Recurse -Force $existingData $dataBackup
}

robocopy (Join-Path $BundleApp "backend") (Join-Path $InstallDir "backend") /MIR /XD .venv __pycache__ .pytest_cache data /NFL /NDL /NJH /NJS /nc /ns /np | Out-Null
# Always copy packaged UI into backend/app/static
$uiSrc = Join-Path $BundleApp "frontend\dist"
$uiDst = Join-Path $InstallDir "backend\app\static"
if (Test-Path $uiSrc) {
  New-Item -ItemType Directory -Force -Path $uiDst | Out-Null
  robocopy $uiSrc $uiDst /MIR /NFL /NDL /NJH /NJS /nc /ns /np | Out-Null
}

if ($dataBackup -and (Test-Path $dataBackup)) {
  New-Item -ItemType Directory -Force -Path $existingData | Out-Null
  robocopy $dataBackup $existingData /E /NFL /NDL /NJH /NJS /nc /ns /np | Out-Null
}

Copy-Item -Force (Join-Path $Root "Start-TDR.cmd") (Join-Path $InstallDir "Start-TDR.cmd")
Copy-Item -Force (Join-Path $Root "Stop-TDR.cmd") (Join-Path $InstallDir "Stop-TDR.cmd")
Copy-Item -Force (Join-Path $Root "Uninstall-TDR.ps1") (Join-Path $InstallDir "Uninstall-TDR.ps1")
Copy-Item -Force (Join-Path $Root "README.txt") (Join-Path $InstallDir "README.txt")
Write-Ok "Files copied"

# --- Virtualenv + deps ---
$VenvPython = Join-Path $InstallDir "backend\.venv\Scripts\python.exe"
$VenvPip = Join-Path $InstallDir "backend\.venv\Scripts\pip.exe"
$BackendDir = Join-Path $InstallDir "backend"

Write-Step "Creating virtual environment"
Push-Location $BackendDir
try {
  if (-not (Test-Path $VenvPython)) {
    & $Python @PythonArgs -m venv .venv
  }
  Write-Ok "venv ready"

  Write-Step "Installing Python packages (this can take several minutes)"
  & $VenvPython -m pip install --upgrade pip wheel setuptools
  # Prefer binary wheels on Windows; CLIP needs git
  $env:PIP_DISABLE_PIP_VERSION_CHECK = "1"
  & $VenvPip install -r requirements.txt
  if ($LASTEXITCODE -ne 0) {
    Write-Warn "Full requirements failed — trying core stack without Paddle/YOLO"
    & $VenvPip install -r requirements-windows-core.txt
    if ($LASTEXITCODE -ne 0) {
      throw "pip install failed. See errors above."
    }
    Write-Warn "Installed core stack only. Stream B OCR/symbol detection may be limited until full deps install."
  } else {
    Write-Ok "Python packages installed"
  }
} finally {
  Pop-Location
}

# --- Shortcuts ---
Write-Step "Creating shortcuts"
$Wsh = New-Object -ComObject WScript.Shell
$StartMenu = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\TDR"
New-Item -ItemType Directory -Force -Path $StartMenu | Out-Null

$startCmd = Join-Path $InstallDir "Start-TDR.cmd"
$lnkStart = $Wsh.CreateShortcut((Join-Path $StartMenu "TDR — Technical Drawing Reader.lnk"))
$lnkStart.TargetPath = $startCmd
$lnkStart.WorkingDirectory = $InstallDir
$lnkStart.Description = "Start TDR"
$lnkStart.Save()

$lnkDesk = $Wsh.CreateShortcut((Join-Path ([Environment]::GetFolderPath("Desktop")) "TDR.lnk"))
$lnkDesk.TargetPath = $startCmd
$lnkDesk.WorkingDirectory = $InstallDir
$lnkDesk.Description = "Start TDR"
$lnkDesk.Save()
Write-Ok "Start Menu + Desktop shortcuts created"

# Marker for uninstall
@"
InstallDir=$InstallDir
InstalledAt=$(Get-Date -Format o)
Version=0.1.0
"@ | Set-Content -Encoding UTF8 (Join-Path $InstallDir "install-info.txt")

Write-Host "`nTDR installed successfully." -ForegroundColor Green
Write-Host "  Folder:  $InstallDir"
Write-Host "  Start:   Desktop shortcut 'TDR' or Start Menu → TDR"
Write-Host "  URL:     http://127.0.0.1:8000/"
Write-Host "  Stop:    Stop-TDR.cmd in the install folder"

if ($StartAfterInstall) {
  Write-Step "Starting TDR"
  Start-Process -FilePath $startCmd
}
