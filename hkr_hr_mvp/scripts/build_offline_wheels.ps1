param([string]$Python = "", [string]$Destination = "")
$ErrorActionPreference = "Stop"
$AppRoot = Split-Path -Parent $PSScriptRoot
if (-not $Python) { $Python = Join-Path $AppRoot ".venv\Scripts\python.exe" }
if (-not $Destination) { $Destination = Join-Path $AppRoot "tmp\offline-wheelhouse" }
New-Item -ItemType Directory -Force -Path $Destination | Out-Null
# Run on the connected development PC, matching production Python/Windows architecture.
& $Python -m pip download --only-binary=:all: --dest $Destination -r (Join-Path $AppRoot "requirements.txt")
if ($LASTEXITCODE -ne 0) { throw "Wheel download failed." }
Copy-Item -LiteralPath (Join-Path $AppRoot "requirements.txt") -Destination (Join-Path $Destination "requirements.txt")
& $Python -c "import sys, platform; print(sys.version); print(platform.machine())" | Set-Content -LiteralPath (Join-Path $Destination "python-version.txt")
Write-Host "Copy this folder to D:\HKR_HR\_system\wheelhouse: $Destination"
