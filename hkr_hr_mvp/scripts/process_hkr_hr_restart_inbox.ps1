param([string]$Root = 'D:\HKR_HR')

$ErrorActionPreference = 'Stop'
$inbox = Join-Path $Root '_system\restart_inbox'
$logs = Join-Path $Root '03.Output\logs\restart_inbox'
$restart = Join-Path $Root 'scripts\restart_hkr_hr_app.ps1'

$request = Get-ChildItem -LiteralPath $inbox -Filter '*.request' -File |
    Where-Object Name -Match '^restart-[0-9a-f]{32}\.request$' |
    Sort-Object CreationTimeUtc, Name | Select-Object -First 1
if (-not $request) { exit 0 }

# Claim before restarting. An interrupted task leaves .running for inspection,
# so the next scheduled run cannot repeat the same restart.
$id = $request.BaseName
$running = Join-Path $inbox "$id.running"
[IO.File]::Move($request.FullName, $running)
$result = [ordered]@{
    request_id = $id
    status = 'failed'
    started_at = [datetime]::UtcNow.ToString('o')
    finished_at = $null
    exit_code = $null
    error = $null
}

try {
    # Only the file name is a signal. No request content is read or executed.
    $process = Start-Process -FilePath "$PSHOME\powershell.exe" -ArgumentList @(
        '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File', "`"$restart`"", '-Root', "`"$Root`"", '-Port', '5000'
    ) -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logs "$id.log") `
        -RedirectStandardError (Join-Path $logs "$id.err.log")
    # Wait for the restart script itself, which launches the persistent web app.
    $null = $process.Handle
    $process.WaitForExit()
    $result.exit_code = $process.ExitCode
    if ($result.exit_code -eq 0) { $result.status = 'succeeded' }
} catch {
    $result.error = $_.Exception.Message
}

$result.finished_at = [datetime]::UtcNow.ToString('o')
$report = Join-Path $logs "$id.result.json"
$result | ConvertTo-Json | Set-Content -LiteralPath "$report.tmp" -Encoding UTF8
[IO.File]::Move("$report.tmp", $report)
Remove-Item -LiteralPath $running
if ($result.status -ne 'succeeded') { exit 1 }
