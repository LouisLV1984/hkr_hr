param(
    [string]$Root = "D:\HKR_HR",
    [string]$Repository = "D:\HKR_HR\04.Backups\short_term_repository",
    [string]$PasswordFile = "D:\HKR_HR\_system\backup\short_term.password"
)

$ErrorActionPreference = "Stop"
$Root = [System.IO.Path]::GetFullPath($Root).TrimEnd('\')
if ($Root -ne "D:\HKR_HR") {
    throw "Short-term production backup only supports D:\HKR_HR."
}

function Resolve-Tool([string]$Name) {
    $command = Get-Command $Name -ErrorAction SilentlyContinue
    if ($command) { return $command.Source }
    $candidates = Get-ChildItem "C:\Program Files\PostgreSQL" -Recurse -Filter "$Name.exe" -File -ErrorAction SilentlyContinue |
        Sort-Object FullName -Descending
    if ($candidates) { return $candidates[0].FullName }
    throw "$Name is not installed or not available in PATH."
}

function Read-DatabaseUrl {
    $envPath = Join-Path $Root "_system\app\.env"
    if (-not (Test-Path -LiteralPath $envPath)) { throw "Production .env not found: $envPath" }
    $line = Get-Content -LiteralPath $envPath | Where-Object { $_ -match '^DATABASE_URL=' } | Select-Object -First 1
    if (-not $line) { throw "DATABASE_URL is missing from production .env." }
    $url = $line.Substring("DATABASE_URL=".Length).Trim() -replace '^postgresql\+psycopg://', 'postgresql://'
    if ($url -notmatch '/hkr_hr_db(?:\?|$)') { throw "Backup target must be hkr_hr_db." }
    return $url
}

$restic = Resolve-Tool "restic"
$pgDump = Resolve-Tool "pg_dump"
if (-not (Test-Path -LiteralPath $PasswordFile)) { throw "Restic password file not found: $PasswordFile" }

$databaseRoot = Join-Path $Root "04.Backups\database"
$logRoot = Join-Path $Root "03.Output\logs"
New-Item -ItemType Directory -Force -Path $databaseRoot, $logRoot | Out-Null
$logPath = Join-Path $logRoot ("backup_short_term_{0}.log" -f (Get-Date -Format "yyyyMMdd_HHmmss"))
$dumpPath = Join-Path $databaseRoot "hkr_hr_db_latest.dump"
$tempDump = "$dumpPath.tmp"

try {
    & $pgDump --format=custom --compress=gzip:6 --file=$tempDump (Read-DatabaseUrl) 2>&1 | Tee-Object -FilePath $logPath -Append
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $tempDump)) { throw "pg_dump failed." }
    Move-Item -LiteralPath $tempDump -Destination $dumpPath -Force

    $sources = @(
        (Join-Path $Root "01.Attachments"),
        (Join-Path $Root "02.Templates"),
        $dumpPath
    )
    & $restic --repo $Repository --password-file $PasswordFile backup @sources --tag hkr-hr-short 2>&1 | Tee-Object -FilePath $logPath -Append
    if ($LASTEXITCODE -ne 0) { throw "Short-term restic backup failed." }
    & $restic --repo $Repository --password-file $PasswordFile forget --keep-daily 7 --prune 2>&1 | Tee-Object -FilePath $logPath -Append
    if ($LASTEXITCODE -ne 0) { throw "Short-term retention cleanup failed." }
    & $restic --repo $Repository --password-file $PasswordFile check 2>&1 | Tee-Object -FilePath $logPath -Append
    if ($LASTEXITCODE -ne 0) { throw "Short-term repository check failed." }
    "Backup completed: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" | Tee-Object -FilePath $logPath -Append
} finally {
    if (Test-Path -LiteralPath $tempDump) { Remove-Item -LiteralPath $tempDump -Force }
}
