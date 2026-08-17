param(
    [ValidateSet("MiniPc", "Laptop")]
    [string]$Mode
)

$ErrorActionPreference = "Stop"

function Ensure-Restic {
    $command = Get-Command restic -ErrorAction SilentlyContinue
    if ($command) { return $command.Source }
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if (-not $winget) { throw "Install restic 0.19 or later, then run this setup again." }
    & $winget.Source install --id restic.restic --exact --silent --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) { throw "restic installation failed." }
    $command = Get-Command restic -ErrorAction SilentlyContinue
    if (-not $command) { throw "restic was installed but is not yet in PATH. Open a new PowerShell window and run setup again." }
    return $command.Source
}

function Ensure-PasswordFile([string]$Path) {
    if (Test-Path -LiteralPath $Path) { return }
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Path) | Out-Null
    $bytes = New-Object byte[] 32
    $generator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $generator.GetBytes($bytes) } finally { $generator.Dispose() }
    $secret = ([System.BitConverter]::ToString($bytes)).Replace("-", "").ToLowerInvariant()
    Set-Content -LiteralPath $Path -Value $secret -NoNewline
    & icacls $Path /inheritance:r /grant:r "${env:USERNAME}:(R,W)" | Out-Null
}

function Ensure-Repository([string]$Restic, [string]$Repository, [string]$PasswordFile) {
    if (Test-Path -LiteralPath (Join-Path $Repository "config")) { return }
    New-Item -ItemType Directory -Force -Path $Repository | Out-Null
    & $Restic --repo $Repository --password-file $PasswordFile init
    if ($LASTEXITCODE -ne 0) { throw "Unable to initialise the backup repository." }
}

$restic = Ensure-Restic
if ($Mode -eq "MiniPc") {
    $repository = "D:\HKR_HR\04.Backups\short_term_repository"
    $passwordFile = "D:\HKR_HR\_system\backup\short_term.password"
    $script = "D:\HKR_HR\scripts\backup_hkr_hr_short_term.ps1"
    $taskName = "HKR HR Short-Term Backup"
    $time = "02:00"
} else {
    $repository = "$env:USERPROFILE\HKR_HR_Backups\repository"
    $passwordFile = "$env:LOCALAPPDATA\HKR_HR_Backup\laptop.password"
    $script = Join-Path $PSScriptRoot "backup_hkr_hr_to_laptop.ps1"
    $taskName = "HKR HR Laptop Backup"
    $time = "03:30"
}

if (-not (Test-Path -LiteralPath $script)) { throw "Backup script not found: $script" }
Ensure-PasswordFile $passwordFile
Ensure-Repository $restic $repository $passwordFile

$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$script`""
$trigger = New-ScheduledTaskTrigger -Daily -At $time
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 6)
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Force | Out-Null

Write-Host "Backup repository: $repository"
Write-Host "Scheduled task:    $taskName at $time (runs when available)"
Write-Host "Password file:     $passwordFile"
