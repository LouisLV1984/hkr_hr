param(
    [int]$Port = 5000,
    [string]$Root = "D:\HKR_HR"
)

$ErrorActionPreference = "Stop"

$Root = (Resolve-Path -LiteralPath $Root).Path
$LogDir = Join-Path $Root "03.Output\logs"
$PidFile = Join-Path $LogDir "hkr_hr_app_$Port.pid"

function Get-ListenerProcessIds {
    param([int]$Port)
    Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        Where-Object { $_.OwningProcess -ne 0 } |
        Select-Object -ExpandProperty OwningProcess -Unique
}

$ProcessIds = @(Get-ListenerProcessIds -Port $Port)

if ($ProcessIds.Count -eq 0 -and (Test-Path -LiteralPath $PidFile)) {
    $SavedPid = (Get-Content -LiteralPath $PidFile -ErrorAction SilentlyContinue | Select-Object -First 1)
    if ($SavedPid -match "^\d+$") {
        $Existing = Get-Process -Id ([int]$SavedPid) -ErrorAction SilentlyContinue
        if ($Existing) {
            $ProcessIds = @([int]$SavedPid)
        }
    }
}

if ($ProcessIds.Count -eq 0) {
    Write-Host "No HKR HR web process is listening on port $Port."
    if (Test-Path -LiteralPath $PidFile) {
        Remove-Item -LiteralPath $PidFile -Force
    }
    exit 0
}

foreach ($ProcessId in $ProcessIds) {
    try {
        Stop-Process -Id $ProcessId -Force -ErrorAction Stop
        Write-Host "Stopped PID $ProcessId"
    } catch {
        Write-Warning "Failed to stop PID $ProcessId : $($_.Exception.Message)"
    }
}

if (Test-Path -LiteralPath $PidFile) {
    Remove-Item -LiteralPath $PidFile -Force
}

Start-Sleep -Seconds 1
$Remaining = @(Get-ListenerProcessIds -Port $Port)
if ($Remaining.Count -gt 0) {
    Write-Warning "Port $Port still has listener PID(s): $($Remaining -join ', ')"
    exit 1
}

Write-Host "HKR HR web app stopped."
