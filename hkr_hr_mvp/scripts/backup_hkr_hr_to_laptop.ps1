param(
    [string]$SourceRoot = "R:\",
    [string]$Repository = "$env:USERPROFILE\HKR_HR_Backups\repository",
    [string]$PasswordFile = "$env:LOCALAPPDATA\HKR_HR_Backup\laptop.password"
)

$ErrorActionPreference = "Stop"
$SourceRoot = [System.IO.Path]::GetFullPath($SourceRoot)
if ([System.IO.Path]::GetPathRoot($SourceRoot) -ne "R:\") {
    throw "Laptop backup source must be the R: production mapping."
}
if (-not (Test-Path -LiteralPath $SourceRoot)) {
    throw "R: is unavailable. Task Scheduler will retry at the next scheduled run."
}

$resticCommand = Get-Command restic -ErrorAction SilentlyContinue
if (-not $resticCommand) { throw "restic is not installed. Run setup_hkr_hr_backup.ps1 first." }
if (-not (Test-Path -LiteralPath $PasswordFile)) { throw "Restic password file not found: $PasswordFile" }

$logRoot = Join-Path $env:LOCALAPPDATA "HKR_HR_Backup\logs"
New-Item -ItemType Directory -Force -Path $logRoot | Out-Null
$logPath = Join-Path $logRoot ("backup_laptop_{0}.log" -f (Get-Date -Format "yyyyMMdd_HHmmss"))
$sources = @(
    (Join-Path $SourceRoot "01.Attachments"),
    (Join-Path $SourceRoot "02.Templates"),
    (Join-Path $SourceRoot "04.Backups\database\hkr_hr_db_latest.dump")
)
foreach ($source in $sources) {
    if (-not (Test-Path -LiteralPath $source)) { throw "Backup source is missing: $source" }
}

& $resticCommand.Source --repo $Repository --password-file $PasswordFile backup @sources --tag hkr-hr-laptop 2>&1 | Tee-Object -FilePath $logPath -Append
if ($LASTEXITCODE -ne 0) { throw "Laptop incremental backup failed." }
& $resticCommand.Source --repo $Repository --password-file $PasswordFile forget --keep-daily 14 --keep-weekly 8 --keep-monthly 12 --prune 2>&1 | Tee-Object -FilePath $logPath -Append
if ($LASTEXITCODE -ne 0) { throw "Laptop retention cleanup failed." }
& $resticCommand.Source --repo $Repository --password-file $PasswordFile check 2>&1 | Tee-Object -FilePath $logPath -Append
if ($LASTEXITCODE -ne 0) { throw "Laptop repository check failed." }

$drive = Get-PSDrive -Name ([System.IO.Path]::GetPathRoot($Repository).Substring(0, 1))
$freePercent = if (($drive.Used + $drive.Free) -gt 0) { 100 * $drive.Free / ($drive.Used + $drive.Free) } else { 0 }
if ($freePercent -lt 15) {
    "WARNING: backup drive free space is below 15%." | Tee-Object -FilePath $logPath -Append
}
"Backup completed: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" | Tee-Object -FilePath $logPath -Append
