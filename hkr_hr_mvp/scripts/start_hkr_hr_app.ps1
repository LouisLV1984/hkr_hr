param(
    [int]$Port = 5000,
    [string]$HostAddress = "0.0.0.0",
    [string]$Root = "D:\HKR_HR",
    [string]$DatabaseUrl = $env:DATABASE_URL,
    [string]$FixedIp = "192.168.128.70",
    [switch]$UseFlaskDevServer
)

$ErrorActionPreference = "Stop"

$Root = (Resolve-Path -LiteralPath $Root).Path
$AppRoot = Join-Path $Root "_system\app"
$VenvRoot = Join-Path $Root "_system\.venv"
$Python = Join-Path $VenvRoot "Scripts\python.exe"
$WaitressExe = Join-Path $VenvRoot "Scripts\waitress-serve.exe"
$LogDir = Join-Path $Root "03.Output\logs"
$PidFile = Join-Path $LogDir "hkr_hr_app_$Port.pid"
$OutLog = Join-Path $LogDir "hkr_hr_app.out.log"
$ErrLog = Join-Path $LogDir "hkr_hr_app.err.log"

function Get-ListenerProcessIds {
    param([int]$Port)
    Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        Where-Object { $_.OwningProcess -ne 0 } |
        Select-Object -ExpandProperty OwningProcess -Unique
}

function Test-LocalHttpReady {
    param([int]$Port)
    try {
        $response = Invoke-WebRequest -Uri "http://127.0.0.1:$Port/login" -UseBasicParsing -TimeoutSec 2
        return ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500)
    } catch {
        if ($_.Exception.Response) {
            $statusCode = [int]$_.Exception.Response.StatusCode
            return ($statusCode -ge 200 -and $statusCode -lt 500)
        }
        return $false
    }
}

if (-not (Test-Path -LiteralPath $Python)) {
    throw "HR Python was not found: $Python"
}
if (-not (Test-Path -LiteralPath (Join-Path $AppRoot "app.py"))) {
    throw "HR Flask app was not found: $AppRoot"
}

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

if (-not [string]::IsNullOrWhiteSpace($DatabaseUrl)) {
    $env:DATABASE_URL = $DatabaseUrl
}

$Existing = @(Get-ListenerProcessIds -Port $Port)
if ($Existing.Count -gt 0) {
    Write-Host "HKR HR web app is already listening on port $Port."
    Write-Host "PID(s): $($Existing -join ', ')"
    exit 0
}

$ServerMode = "waitress"
$ServerExe = $Python
$Arguments = @("-m", "waitress", "--listen=$HostAddress`:$Port", "app:app")

if ((Test-Path -LiteralPath $WaitressExe) -and -not $UseFlaskDevServer) {
    $ServerExe = $WaitressExe
    $Arguments = @("--listen=$HostAddress`:$Port", "app:app")
}

if ($UseFlaskDevServer) {
    $ServerMode = "flask-dev"
    $ServerExe = $Python
    $Arguments = @("app.py")
}

Write-Host "Starting HKR HR web app with server mode: $ServerMode"

$Process = Start-Process `
    -FilePath $ServerExe `
    -ArgumentList $Arguments `
    -WorkingDirectory $AppRoot `
    -WindowStyle Hidden `
    -RedirectStandardOutput $OutLog `
    -RedirectStandardError $ErrLog `
    -PassThru

$Process.Id | Set-Content -LiteralPath $PidFile -Encoding ASCII
$Started = @()
$Ready = $false
$Deadline = (Get-Date).AddSeconds(25)
while ((Get-Date) -lt $Deadline) {
    if ($Process.HasExited) {
        break
    }
    $Started = @(Get-ListenerProcessIds -Port $Port)
    if ($Started.Count -gt 0 -or (Test-LocalHttpReady -Port $Port)) {
        $Ready = $true
        break
    }
    Start-Sleep -Seconds 1
}

if ($Started.Count -eq 0) {
    $Started = @(Get-ListenerProcessIds -Port $Port)
}

if (-not $Ready -and $Started.Count -eq 0) {
    Write-Host "HKR HR web app failed to start on port $Port."
    if ($Process.HasExited) {
        Write-Host "Process exited early with code $($Process.ExitCode)."
    }
    if (Test-Path -LiteralPath $ErrLog) {
        Write-Host ""
        Write-Host "Error log tail:"
        Get-Content -LiteralPath $ErrLog -Tail 40
    }
    exit 1
}

Write-Host "HKR HR web app started."
Write-Host "Server mode: $ServerMode"
Write-Host "PID(s):      $($Started -join ', ')"
Write-Host "Root:        $Root"
Write-Host "App root:    $AppRoot"
Write-Host "Venv root:   $VenvRoot"
Write-Host "Database:    PostgreSQL hkr_hr_db"
Write-Host "Local URL:   http://127.0.0.1:$Port/login"
Write-Host "Fixed URL:   http://$FixedIp`:$Port/login"

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
    Write-Host "LAN URL:     http://$Address`:$Port/login"
}

Write-Host "Logs:"
Write-Host "  $OutLog"
Write-Host "  $ErrLog"
