param(
    [string]$Root = "D:\HKR_HR",
    [switch]$Recreate
)

$ErrorActionPreference = "Stop"

$Root = (Resolve-Path -LiteralPath $Root).Path
$AppRoot = Join-Path $Root "_system\app"
$VenvRoot = Join-Path $Root "_system\.venv"
$Requirements = Join-Path $AppRoot "requirements.txt"
$ReadyMarker = Join-Path $VenvRoot ".hkr_hr_venv_ready"
$HashMarker = Join-Path $VenvRoot ".hkr_hr_requirements_sha256"

if (-not (Test-Path -LiteralPath (Join-Path $AppRoot "app.py"))) {
    throw "HR app root is not ready: $AppRoot"
}
if (-not (Test-Path -LiteralPath $Requirements)) {
    throw "Requirements file was not found: $Requirements"
}

$RequirementsHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $Requirements).Hash

if ((Test-Path -LiteralPath $VenvRoot) -and $Recreate) {
    $backup = Join-Path (Split-Path -Parent $VenvRoot) (".venv.backup_" + (Get-Date -Format "yyyyMMdd_HHmmss"))
    Move-Item -LiteralPath $VenvRoot -Destination $backup
    Write-Host "Existing HR venv moved to: $backup"
}

$Python = Join-Path $VenvRoot "Scripts\python.exe"

if ((Test-Path -LiteralPath $ReadyMarker) -and
    (Test-Path -LiteralPath $HashMarker) -and
    (Test-Path -LiteralPath $Python)) {
    $ExistingHash = (Get-Content -LiteralPath $HashMarker -Raw).Trim()
    if ($ExistingHash -eq $RequirementsHash) {
        & $Python -c "import flask, flask_login, flask_sqlalchemy, docxtpl, openpyxl, psycopg, waitress, pytesseract, pdf2image; import PIL; print('HR venv import check passed')"
        if ($LASTEXITCODE -eq 0) {
            Write-Host "HR venv is already ready and requirements are current: $VenvRoot"
            exit 0
        }
    }
}

$SeedCandidates = @(
    $Python,
    (Join-Path $Root ".venv\Scripts\python.exe"),
    "py",
    "python"
)

$SeedPython = ""
foreach ($candidate in $SeedCandidates) {
    try {
        if ($candidate -eq "py") {
            & py -3 -c "import sys; print(sys.executable)" | Out-Null
            if ($LASTEXITCODE -eq 0) {
                $SeedPython = "py -3"
                break
            }
        } elseif ($candidate -eq "python") {
            & python -c "import sys; print(sys.executable)" | Out-Null
            if ($LASTEXITCODE -eq 0) {
                $SeedPython = "python"
                break
            }
        } elseif (Test-Path -LiteralPath $candidate) {
            & $candidate -c "import sys; print(sys.executable)" | Out-Null
            if ($LASTEXITCODE -eq 0) {
                $SeedPython = $candidate
                break
            }
        }
    } catch {
        continue
    }
}

if (-not $SeedPython) {
    throw "No usable Python was found for creating the HR venv."
}

Write-Host "Preparing HR system venv:"
Write-Host "  Root:     $Root"
Write-Host "  AppRoot:  $AppRoot"
Write-Host "  VenvRoot: $VenvRoot"
Write-Host "  Python:   $SeedPython"

if (-not (Test-Path -LiteralPath $Python)) {
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $VenvRoot) | Out-Null
    if ($SeedPython -eq "py -3") {
        & py -3 -m venv $VenvRoot
    } elseif ($SeedPython -eq "python") {
        & python -m venv $VenvRoot
    } else {
        & $SeedPython -m venv $VenvRoot
    }
    if ($LASTEXITCODE -ne 0) {
        throw "venv creation failed."
    }
} else {
    Write-Host "Using existing HR venv: $VenvRoot"
}

& $Python -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) {
    throw "pip upgrade failed."
}

& $Python -m pip install --only-binary=:all: -r $Requirements
if ($LASTEXITCODE -ne 0) {
    throw "requirements install failed."
}

& $Python -c "import flask, flask_login, flask_sqlalchemy, docxtpl, openpyxl, psycopg, waitress, pytesseract, pdf2image; import PIL; print('HR venv import check passed')"
if ($LASTEXITCODE -ne 0) {
    throw "HR venv import check failed."
}

Set-Content -LiteralPath $HashMarker -Value $RequirementsHash -Encoding ASCII
Set-Content -LiteralPath $ReadyMarker -Value (Get-Date -Format "yyyy-MM-dd HH:mm:ss") -Encoding ASCII
Write-Host "HR venv ready: $VenvRoot"
