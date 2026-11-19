param(
    [string]$ProductionRoot = 'R:\',
    [ValidatePattern('^restart-[0-9a-f]{32}$')]
    [string]$RequestId,
    [ValidateRange(0, 3600)]
    [int]$WaitSeconds = 120
)

$ErrorActionPreference = 'Stop'
$inbox = Join-Path $ProductionRoot '_system\restart_inbox'
$logs = Join-Path $ProductionRoot '03.Output\logs\restart_inbox'

if (-not $RequestId) {
    if (-not (Test-Path -LiteralPath (Join-Path $ProductionRoot 'scripts\process_hkr_hr_restart_inbox.ps1') -PathType Leaf)) {
        throw 'The HKR HR restart inbox scripts have not been deployed to this root.'
    }
    $RequestId = 'restart-' + [guid]::NewGuid().ToString('N')
    New-Item -ItemType Directory -Path $inbox -Force | Out-Null
    New-Item -ItemType File -Path (Join-Path $inbox "$RequestId.request") | Out-Null
    Write-Host "Queued HKR HR restart: $RequestId"
    if ($WaitSeconds -eq 0) { return }
}

$report = Join-Path $logs "$RequestId.result.json"
$deadline = [datetime]::UtcNow.AddSeconds($WaitSeconds)
do {
    if (Test-Path -LiteralPath $report -PathType Leaf) {
        $result = Get-Content -LiteralPath $report -Raw | ConvertFrom-Json
        $result | ConvertTo-Json
        if ($result.status -ne 'succeeded') { exit 1 }
        exit 0
    }
    if ([datetime]::UtcNow -ge $deadline) { break }
    Start-Sleep -Seconds 2
} while ($true)

$state = 'not found'
if (Test-Path -LiteralPath (Join-Path $inbox "$RequestId.request")) { $state = 'queued' }
if (Test-Path -LiteralPath (Join-Path $inbox "$RequestId.running")) { $state = 'started; awaiting result' }
Write-Host "HKR HR restart $RequestId : $state. Check the same ID with -RequestId to avoid a second restart."
exit 2
