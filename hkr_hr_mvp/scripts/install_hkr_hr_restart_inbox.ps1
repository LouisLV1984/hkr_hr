$ErrorActionPreference = 'Stop'
$root = 'D:\HKR_HR'
$worker = Join-Path $root 'scripts\process_hkr_hr_restart_inbox.ps1'
$restart = Join-Path $root 'scripts\restart_hkr_hr_app.ps1'
$taskName = 'HKR HR Restart Inbox'

if (!(Test-Path -LiteralPath $worker -PathType Leaf) -or
    !(Test-Path -LiteralPath $restart -PathType Leaf) -or
    !(Test-Path -LiteralPath (Join-Path $root '_system\app\.env') -PathType Leaf)) {
    throw 'Run this installer on the HKR HR mini PC after deployment.'
}

New-Item -ItemType Directory -Force -Path (Join-Path $root '_system\restart_inbox'),
    (Join-Path $root '03.Output\logs\restart_inbox') | Out-Null

$account = [Security.Principal.WindowsIdentity]::GetCurrent().Name
$principal = New-ScheduledTaskPrincipal -UserId $account -LogonType Interactive -RunLevel Limited
$action = New-ScheduledTaskAction -Execute "$PSHOME\powershell.exe" `
    -Argument "-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$worker`""
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 1)
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 15)
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Force | Out-Null
Start-ScheduledTask -TaskName $taskName

Write-Host "Installed $taskName for $account. It will process pending restarts while this account is signed in."
