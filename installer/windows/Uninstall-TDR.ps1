#Requires -Version 5.1
<#
.SYNOPSIS
  Remove TDR from this Windows user profile.
#>
[CmdletBinding()]
param(
  [string]$InstallDir = "$env:LOCALAPPDATA\Programs\TDR"
)

$ErrorActionPreference = "Stop"

Write-Host "Stopping TDR if running…"
Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue |
  ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }

if (Test-Path $InstallDir) {
  Write-Host "Removing $InstallDir"
  Remove-Item -Recurse -Force $InstallDir
}

$desk = Join-Path ([Environment]::GetFolderPath("Desktop")) "TDR.lnk"
if (Test-Path $desk) { Remove-Item -Force $desk }

$startMenu = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\TDR"
if (Test-Path $startMenu) { Remove-Item -Recurse -Force $startMenu }

Write-Host "TDR uninstalled." -ForegroundColor Green
