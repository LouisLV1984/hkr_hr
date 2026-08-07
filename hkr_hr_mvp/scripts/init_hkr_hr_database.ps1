param(
    [string]$Root = "D:\HKR_HR",
    [string]$Username = "admin",
    [string]$Password = $env:HKR_HR_ADMIN_PASSWORD,
    [switch]$ResetAdminPassword,
    [switch]$Reset
)

$ErrorActionPreference = "Stop"

$Root = (Resolve-Path -LiteralPath $Root).Path
$ScriptRoot = Join-Path $Root "scripts"
$AppRoot = Join-Path $Root "_system\app"
$Python = Join-Path $Root "_system\.venv\Scripts\python.exe"
$Bootstrap = Join-Path $AppRoot "scripts\bootstrap_production_db.py"

Write-Host "HKR HR database bootstrap"
Write-Host "Root:     $Root"
Write-Host "Database: hkr_hr_db"
Write-Host "User:     $Username"
Write-Host "Reset password: $ResetAdminPassword"
Write-Host "Reset tables:   $Reset"
Write-Host ""

if (-not (Test-Path -LiteralPath (Join-Path $AppRoot ".env"))) {
    throw "Production .env was not found: $(Join-Path $AppRoot ".env")"
}
if (-not (Test-Path -LiteralPath (Join-Path $ScriptRoot "setup_system_venv.ps1"))) {
    throw "setup_system_venv.ps1 was not found under $ScriptRoot"
}

& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $ScriptRoot "setup_system_venv.ps1") -Root $Root
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Python venv was not found: $Python"
}
if (-not (Test-Path -LiteralPath $Bootstrap)) {
    throw "Bootstrap script was not found: $Bootstrap"
}
if ($ResetAdminPassword -and [string]::IsNullOrWhiteSpace($Password)) {
    throw "HKR_HR_ADMIN_PASSWORD or -Password is required with -ResetAdminPassword."
}

$bootstrapArgs = @($Bootstrap, "--username", $Username)
if (-not [string]::IsNullOrWhiteSpace($Password)) {
    $env:ADMIN_PASSWORD = $Password
}
if ($ResetAdminPassword) {
    $bootstrapArgs += "--reset-admin-password"
}
if ($Reset) {
    $bootstrapArgs += @("--reset", "--confirm-reset", "hkr_hr_db")
}

& $Python @bootstrapArgs
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "HKR HR database is ready."
Write-Host "Login:"
Write-Host "  URL:      http://192.168.128.70:5000/login"
Write-Host "  Username: $Username"
