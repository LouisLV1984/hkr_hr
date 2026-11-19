param(
    [int]$Port = 5000,
    [string]$Root = "D:\HKR_HR",
    [string]$FixedIp = "192.168.128.70"
)

$ErrorActionPreference = "Stop"

$Root = (Resolve-Path -LiteralPath $Root).Path
$LogDir = Join-Path $Root "03.Output\logs"
$PidFile = Join-Path $LogDir "hkr_hr_app_$Port.pid"
$OutLog = Join-Path $LogDir "hkr_hr_app.out.log"
$ErrLog = Join-Path $LogDir "hkr_hr_app.err.log"

$HttpReady = $false
try {
    $response = Invoke-WebRequest -Uri "http://127.0.0.1:$Port/login" -UseBasicParsing -TimeoutSec 5
    $HttpReady = $response.StatusCode -eq 200
} catch { }
if ($HttpReady) { Write-Host "HKR HR web app responds normally on port $Port." }
else { Write-Host "HKR HR web app did not return a successful login page on port $Port." }

$Connections = @(Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue)
$Listeners = @($Connections | Where-Object { $_.State -eq "Listen" -and $_.OwningProcess -ne 0 })

if ($Listeners.Count -eq 0) {
    Write-Host "Windows did not return listener details; use the HTTP result above."
} else {
    Write-Host "HKR HR web app listener(s):"
    $Listeners | Select-Object LocalAddress, LocalPort, State, OwningProcess | Format-Table -AutoSize

    $ProcessIds = @($Listeners | Select-Object -ExpandProperty OwningProcess -Unique)
    foreach ($ProcessId in $ProcessIds) {
        $Process = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
        if ($Process) {
            Write-Host "PID ${ProcessId}: $($Process.ProcessName), started $($Process.StartTime)"
        }
    }
}

if (Test-Path -LiteralPath $PidFile) {
    Write-Host "PID file: $PidFile = $((Get-Content -LiteralPath $PidFile | Select-Object -First 1))"
}

Write-Host "Root:      $Root"
Write-Host "Local URL: http://127.0.0.1:$Port/login"
Write-Host "Fixed URL: http://$FixedIp`:$Port/login"

$LanAddresses = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
    Where-Object {
        $_.IPAddress -ne "127.0.0.1" -and
        $_.IPAddress -notlike "169.254*" -and
        $_.InterfaceAlias -notlike "*Tailscale*" -and
        $_.InterfaceAlias -notlike "*VPN*" -and
        $_.InterfaceAlias -notlike "*OpenVPN*"
    } |
    Select-Object -ExpandProperty IPAddress

foreach ($Address in $LanAddresses) {
    Write-Host "LAN URL:   http://$Address`:$Port/login"
}

Write-Host "Logs:"
Write-Host "  $OutLog"
Write-Host "  $ErrLog"

if (Test-Path -LiteralPath $ErrLog) {
    Write-Host ""
    Write-Host "Error log tail:"
    Get-Content -LiteralPath $ErrLog -Tail 20
}

if (-not $HttpReady) { exit 1 }
