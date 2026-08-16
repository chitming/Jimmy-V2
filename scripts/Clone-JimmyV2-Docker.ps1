#Requires -Version 5.1
<#
.SYNOPSIS
  Clone Jimmy-V2 and run it in Docker Desktop as container "jimmy-v2".

.EXAMPLE
  Right-click → Run with PowerShell
  Or: powershell -ExecutionPolicy Bypass -File .\Clone-JimmyV2-Docker.ps1
#>
[CmdletBinding()]
param(
  [string]$TargetDir = "$env:USERPROFILE\Jimmy-V2",
  [string]$RepoUrl = "https://github.com/chitming/Jimmy-V2.git",
  [string]$Branch = "cursor/sheetsense-layout-mvp-f8ab",
  [ValidateSet("full", "slim")]
  [string]$Profile = "slim",
  [switch]$SkipClone
)

$ErrorActionPreference = "Stop"

function Assert-Command($Name) {
  if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
    throw "Required command not found: $Name"
  }
}

Write-Host "Jimmy-V2 → local Docker (name: jimmy-v2)" -ForegroundColor Cyan

Assert-Command "git"
Assert-Command "docker"

$dockerInfo = docker info 2>&1
if ($LASTEXITCODE -ne 0) {
  throw "Docker is not running. Start Docker Desktop, then re-run this script."
}

if (-not $SkipClone) {
  if (Test-Path (Join-Path $TargetDir ".git")) {
    Write-Host "==> Repo exists at $TargetDir — pulling latest"
    Push-Location $TargetDir
    git fetch origin
    git checkout $Branch
    git pull origin $Branch
    Pop-Location
  } else {
    Write-Host "==> Cloning $RepoUrl ($Branch) → $TargetDir"
    New-Item -ItemType Directory -Force -Path (Split-Path $TargetDir -Parent) | Out-Null
    git clone --branch $Branch $RepoUrl $TargetDir
  }
}

if (-not (Test-Path (Join-Path $TargetDir "docker-compose.yml"))) {
  throw "docker-compose.yml not found in $TargetDir. Clone may have failed."
}

Push-Location $TargetDir
try {
  Write-Host "==> Stopping any old jimmy-v2 / tdr containers on port 8000"
  docker rm -f jimmy-v2 jimmy-v2-slim tdr tdr-slim 2>$null | Out-Null

  if ($Profile -eq "slim") {
    Write-Host "==> Building and starting jimmy-v2 (slim)"
    docker compose --profile slim up --build -d jimmy-v2-slim
  } else {
    Write-Host "==> Building and starting jimmy-v2 (full)"
    docker compose up --build -d jimmy-v2
  }

  Write-Host "==> Waiting for http://localhost:8000/"
  $ok = $false
  for ($i = 0; $i -lt 90; $i++) {
    try {
      $r = Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:8000/api/stats" -TimeoutSec 2
      if ($r.StatusCode -eq 200) { $ok = $true; break }
    } catch { }
    Start-Sleep -Seconds 2
  }

  if (-not $ok) {
    Write-Host "Container started but API not ready yet. Check: docker logs jimmy-v2" -ForegroundColor Yellow
  } else {
    Write-Host "Jimmy-V2 is running." -ForegroundColor Green
    Start-Process "http://localhost:8000/"
  }

  Write-Host ""
  Write-Host "Container name : jimmy-v2 (or jimmy-v2-slim)"
  Write-Host "Code folder    : $TargetDir"
  Write-Host "URL            : http://localhost:8000/"
  Write-Host "Stop           : docker compose -f `"$TargetDir\docker-compose.yml`" down"
} finally {
  Pop-Location
}
