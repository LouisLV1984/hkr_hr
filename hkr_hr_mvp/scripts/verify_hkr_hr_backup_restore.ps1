param(
    [ValidateSet("MiniPc", "Laptop")]
    [string]$Mode = "MiniPc",
    [string]$RestoreRoot = "D:\HKR_HR\04.Backups\restore_test"
)

$ErrorActionPreference = "Stop"
if ($Mode -eq "MiniPc") {
    $repository = "D:\HKR_HR\04.Backups\short_term_repository"
    $passwordFile = "D:\HKR_HR\_system\backup\short_term.password"
    $envPath = "D:\HKR_HR\_system\app\.env"
} else {
    $repository = "$env:USERPROFILE\HKR_HR_Backups\repository"
    $passwordFile = "$env:LOCALAPPDATA\HKR_HR_Backup\laptop.password"
    $envPath = "R:\_system\app\.env"
    if ($RestoreRoot -eq "D:\HKR_HR\04.Backups\restore_test") {
        $RestoreRoot = Join-Path $env:TEMP "HKR_HR_restore_test"
    }
}

$restic = (Get-Command restic -ErrorAction Stop).Source
$pgRestore = (Get-Command pg_restore -ErrorAction SilentlyContinue).Source
if (-not $pgRestore) {
    $pgRestore = (Get-ChildItem "C:\Program Files\PostgreSQL" -Recurse -Filter "pg_restore.exe" -File | Sort-Object FullName -Descending | Select-Object -First 1).FullName
}
if (-not $pgRestore) { throw "pg_restore is not available." }
if (-not (Test-Path -LiteralPath $passwordFile)) { throw "Backup password file not found." }

$resolvedRestoreRoot = [System.IO.Path]::GetFullPath($RestoreRoot)
if ($resolvedRestoreRoot -notmatch '(?i)hkr_hr.*restore_test') {
    throw "Restore test target must contain hkr_hr and restore_test."
}
New-Item -ItemType Directory -Force -Path $resolvedRestoreRoot | Out-Null

& $restic --repo $repository --password-file $passwordFile check
if ($LASTEXITCODE -ne 0) { throw "Repository integrity check failed." }
& $restic --repo $repository --password-file $passwordFile restore latest --target $resolvedRestoreRoot --include "*hkr_hr_db_latest.dump" --include "*02.Templates*"
if ($LASTEXITCODE -ne 0) { throw "Restore test extraction failed." }

$dump = Get-ChildItem -LiteralPath $resolvedRestoreRoot -Recurse -Filter "hkr_hr_db_latest.dump" -File | Select-Object -First 1
if (-not $dump) { throw "Restored PostgreSQL dump was not found." }
& $pgRestore --list $dump.FullName | Out-Null
if ($LASTEXITCODE -ne 0) { throw "PostgreSQL dump cannot be read by pg_restore." }
$template = Get-ChildItem -LiteralPath $resolvedRestoreRoot -Recurse -Include "*.xlsx", "*.docx" -File | Select-Object -First 1
if (-not $template -or $template.Length -le 0) { throw "No usable restored template was found." }

if ($Mode -eq "MiniPc") {
    $line = Get-Content -LiteralPath $envPath | Where-Object { $_ -match '^DATABASE_URL=' } | Select-Object -First 1
    if (-not $line) { throw "DATABASE_URL is missing from production .env." }
    $sourceUrl = $line.Substring("DATABASE_URL=".Length).Trim() -replace '^postgresql\+psycopg://', 'postgresql://'
    if ($sourceUrl -notmatch '^(postgresql://.+/)(hkr_hr_db)(\?.*)?$') {
        throw "Restore verification only accepts hkr_hr_db as the source database."
    }
    $prefix = $Matches[1]
    $query = $Matches[3]
    $testDatabase = "hkr_hr_restore_test_{0}" -f (Get-Date -Format "yyyyMMddHHmmss")
    $maintenanceUrl = "${prefix}postgres${query}"
    $testUrl = "${prefix}${testDatabase}${query}"
    $createdb = Join-Path (Split-Path -Parent $pgRestore) "createdb.exe"
    $dropdb = Join-Path (Split-Path -Parent $pgRestore) "dropdb.exe"
    $psql = Join-Path (Split-Path -Parent $pgRestore) "psql.exe"
    foreach ($tool in @($createdb, $dropdb, $psql)) {
        if (-not (Test-Path -LiteralPath $tool)) { throw "PostgreSQL restore tool not found: $tool" }
    }
    try {
        & $createdb --maintenance-db=$maintenanceUrl $testDatabase
        if ($LASTEXITCODE -ne 0) { throw "Unable to create isolated restore database." }
        & $pgRestore --dbname=$testUrl --no-owner --no-privileges $dump.FullName
        if ($LASTEXITCODE -ne 0) { throw "PostgreSQL restore into the isolated database failed." }
        $employeeCount = (& $psql --dbname=$testUrl --no-align --tuples-only --command "SELECT COUNT(*) FROM employees;").Trim()
        if ($LASTEXITCODE -ne 0 -or $employeeCount -notmatch '^\d+$') {
            throw "Restored employee table could not be queried."
        }
        Write-Host "Restored employee rows: $employeeCount"
    } finally {
        & $dropdb --maintenance-db=$maintenanceUrl --if-exists $testDatabase | Out-Null
    }
}

Write-Host "Restore verification passed."
Write-Host "Dump:     $($dump.FullName)"
Write-Host "Template: $($template.FullName)"

if ($Mode -eq "MiniPc") {
    $logRoot = "D:\HKR_HR\03.Output\logs"
} else {
    $logRoot = Join-Path $env:LOCALAPPDATA "HKR_HR_Backup\logs"
}
New-Item -ItemType Directory -Force -Path $logRoot | Out-Null
$verificationLog = Join-Path $logRoot ("restore_verify_{0}.log" -f (Get-Date -Format "yyyyMMdd_HHmmss"))
@(
    "Restore verification passed."
    "Verified at: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
    "Mode: $Mode"
    "Dump: $($dump.Name)"
    "Template: $($template.Name)"
) | Set-Content -LiteralPath $verificationLog -Encoding UTF8
