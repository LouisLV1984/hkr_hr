param(
    [int]$Port = 5000,
    [string]$RuleName = "HKR HR Web App (TCP 5000)"
)

$ErrorActionPreference = "Stop"

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
$isAdmin = $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    throw "Please run this script as Administrator."
}

$existingRules = @(Get-NetFirewallRule -DisplayName $RuleName -ErrorAction SilentlyContinue)
if ($existingRules.Count -gt 0) {
    $existingRules | Set-NetFirewallRule -Enabled True -Profile Any -Action Allow
    $existingRules | Get-NetFirewallPortFilter | Set-NetFirewallPortFilter -Protocol TCP -LocalPort $Port
    Write-Host "Updated existing firewall rule: $RuleName"
} else {
    New-NetFirewallRule `
        -DisplayName $RuleName `
        -Direction Inbound `
        -Action Allow `
        -Protocol TCP `
        -LocalPort $Port `
        -Profile Any | Out-Null
    Write-Host "Created firewall rule: $RuleName"
}

Write-Host "HKR HR fixed URL:"
Write-Host "http://192.168.128.70:$Port/login"
