param(
    [string]$Root = "D:\HKR_HR",
    [int]$Port = 5000
)

$ErrorActionPreference = "Stop"

$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "HKR HR Operating Console - setup venv and restart web app"
Write-Host "Root: $Root"
Write-Host "Port: $Port"
Write-Host "Database: PostgreSQL local hkr_hr_db"
Write-Host ""

& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $ScriptRoot "setup_system_venv.ps1") -Root $Root
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $ScriptRoot "init_hkr_hr_database.ps1") -Root $Root -Username "admin"
if ($LASTEXITCODE -eq 20) {
    Write-Host ""
    Write-Host "The old HKR HR test schema requires a one-time V1 rebuild."
    Write-Host "Run: $Root\scripts\mini_pc_upgrade_hkr_hr_v1_and_restart.bat"
    exit 20
}
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $ScriptRoot "stop_hkr_hr_app.ps1") -Port $Port -Root $Root
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $ScriptRoot "start_hkr_hr_app.ps1") -Port $Port -Root $Root
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $ScriptRoot "status_hkr_hr_app.ps1") -Port $Port -Root $Root
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
