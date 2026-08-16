#Requires -Version 5.1
# Load the Jimmy-V2 image into local Docker Desktop and start it.
# Place this script next to jimmy-v2-slim.tar.gz (or jimmy-v2-latest.tar.gz), then:
#   powershell -ExecutionPolicy Bypass -File .\Load-Jimmy-V2.ps1
param(
  [ValidateSet("slim", "latest")]
  [string]$Tag = "slim"
)

$ErrorActionPreference = "Stop"
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Archive = Join-Path $Here "jimmy-v2-$Tag.tar.gz"
if (-not (Test-Path $Archive)) {
  $Archive = Join-Path (Split-Path $Here -Parent) "jimmy-v2-$Tag.tar.gz"
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
  throw "Docker is not installed. Install Docker Desktop first."
}
docker info 1>$null 2>$null
if ($LASTEXITCODE -ne 0) {
  throw "Docker Desktop is not running. Start it, then re-run this script."
}
if (-not (Test-Path $Archive)) {
  throw "Missing jimmy-v2-$Tag.tar.gz next to this script (or in the repo root). Download it from the agent artifacts."
}

Write-Host "==> Loading image jimmy-v2:$Tag from $Archive"
docker load -i $Archive

Write-Host "==> Starting container jimmy-v2"
docker rm -f jimmy-v2 jimmy-v2-slim tdr tdr-slim 2>$null | Out-Null
docker run --name jimmy-v2 -d -p 8000:8000 -v jimmy-v2-data:/app/data --restart unless-stopped "jimmy-v2:$Tag"

Write-Host "Jimmy-V2 is running as image/container jimmy-v2"
Write-Host "Open http://localhost:8000/"
Start-Process "http://localhost:8000/"
