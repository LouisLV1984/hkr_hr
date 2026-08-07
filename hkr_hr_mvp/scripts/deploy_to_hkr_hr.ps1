param(
    [string]$ProductionRoot = "R:\",
    [switch]$SkipCompile
)

$ErrorActionPreference = "Stop"

$SourceRoot = Split-Path -Parent $PSScriptRoot
$ProductionRoot = [System.IO.Path]::GetFullPath($ProductionRoot)
$rootOnly = [System.IO.Path]::GetPathRoot($ProductionRoot)
if ($ProductionRoot.TrimEnd('\', '/') -ne $rootOnly.TrimEnd('\', '/')) {
    $ProductionRoot = $ProductionRoot.TrimEnd("\", "/")
}
$AppTarget = Join-Path $ProductionRoot "_system\app"
$OperatorScriptTarget = Join-Path $ProductionRoot "scripts"
$TemplateTarget = Join-Path $ProductionRoot "02.Templates\contract_templates"
$PayrollTemplateTarget = Join-Path $ProductionRoot "02.Templates\payroll"
$AttachmentRoot = Join-Path $ProductionRoot "01.Attachments"
$OutputRoot = Join-Path $ProductionRoot "03.Output"
$GeneratedRoot = Join-Path $OutputRoot "generated_contracts"
$LogRoot = Join-Path $OutputRoot "logs"
$DeployLogRoot = Join-Path $SourceRoot "tmp\deploy_logs"
$RootShortcutTarget = Join-Path $ProductionRoot "HKR_HR_Web.url"
$UserGuideName = (-join @(
    [char]0x64CD,
    [char]0x4F5C,
    [char]0x6307,
    [char]0x5357
)) + ".md"
$UserGuideSource = Join-Path $SourceRoot $UserGuideName
$UserGuideTarget = Join-Path $ProductionRoot $UserGuideName
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$LogPath = Join-Path $DeployLogRoot "deploy_to_hkr_hr_$Timestamp.log"

New-Item -ItemType Directory -Force -Path $DeployLogRoot, $AppTarget, $OperatorScriptTarget, $TemplateTarget, $PayrollTemplateTarget, $AttachmentRoot, $GeneratedRoot, $LogRoot | Out-Null

function Write-DeployLog {
    param([string]$Message)
    $Message | Tee-Object -FilePath $LogPath -Append
}

function Convert-ToRelativePath {
    param([string]$Root, [string]$Path)
    $rootFull = [System.IO.Path]::GetFullPath($Root).TrimEnd('\', '/')
    $pathFull = [System.IO.Path]::GetFullPath($Path)
    if (-not $pathFull.StartsWith($rootFull, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Path is outside source root: $Path"
    }
    return $pathFull.Substring($rootFull.Length).TrimStart('\', '/')
}

function Test-DeployablePath {
    param([string]$RelativePath)
    $normalized = $RelativePath.Replace("/", "\").TrimStart('\')
    $excludedPrefixes = @(
        ".venv\",
        ".tmp\",
        "__pycache__\",
        "_backups\",
        "_verification\",
        "docs\",
        "employee_attachments\",
        "uploads\",
        "generated_contracts\",
        "contract_templates\",
        "payroll_templates\",
        "node_modules\",
        "tests\",
        "tmp\"
    )
    $excludedNames = @(
        ".env",
        "HKR_HR_Web.url",
        "flask_stdout.log",
        "flask_stderr.log",
        "deploy_to_hkr_hr.ps1",
        "mini_pc_restart_hkr_hr_app.bat",
        "mini_pc_upgrade_hkr_hr_v1_and_restart.bat",
        "restart_hkr_hr_app.ps1",
        "setup_system_venv.ps1",
        "start_hkr_hr_app.ps1",
        "stop_hkr_hr_app.ps1",
        "status_hkr_hr_app.ps1",
        "open_hkr_hr_web.bat",
        "allow_hkr_hr_firewall_port.ps1",
        "allow_hkr_hr_firewall_port_admin.bat",
        "init_hkr_hr_database.ps1",
        "mini_pc_init_hkr_hr_database.bat"
    )
    foreach ($prefix in $excludedPrefixes) {
        if ($normalized.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)) {
            return $false
        }
    }
    if ($normalized -match "(^|\\)__pycache__(\\|$)") {
        return $false
    }
    if ($excludedNames -contains (Split-Path -Leaf $normalized)) {
        return $false
    }
    return $true
}

Write-DeployLog "HKR HR deployment"
Write-DeployLog "Source:     $SourceRoot"
Write-DeployLog "Target app: $AppTarget"
Write-DeployLog "Templates:  $TemplateTarget"
Write-DeployLog "Payroll templates: $PayrollTemplateTarget"

if (-not $SkipCompile) {
    Write-DeployLog "Running Python compile check..."
    $python = Join-Path $SourceRoot ".venv\Scripts\python.exe"
    if (-not (Test-Path -LiteralPath $python)) {
        $python = "python"
    }
    & $python -m py_compile `
        (Join-Path $SourceRoot "app.py") `
        (Join-Path $SourceRoot "config.py") `
        (Join-Path $SourceRoot "models.py") `
        (Join-Path $SourceRoot "routes\admin.py") `
        (Join-Path $SourceRoot "routes\auth.py") `
        (Join-Path $SourceRoot "routes\dashboard.py") `
        (Join-Path $SourceRoot "routes\documents.py") `
        (Join-Path $SourceRoot "routes\employees.py") `
        (Join-Path $SourceRoot "routes\exports.py") `
        (Join-Path $SourceRoot "routes\attendance.py") `
        (Join-Path $SourceRoot "routes\leave.py") `
        (Join-Path $SourceRoot "routes\payroll.py") `
        (Join-Path $SourceRoot "routes\references.py") `
        (Join-Path $SourceRoot "scripts\init_db.py") `
        (Join-Path $SourceRoot "scripts\bootstrap_production_db.py") `
        (Join-Path $SourceRoot "scripts\seed_acceptance_data.py") `
        (Join-Path $SourceRoot "tools\hr_core.py") `
        (Join-Path $SourceRoot "tools\i18n.py") `
        (Join-Path $SourceRoot "tools\payroll_engine.py") `
        (Join-Path $SourceRoot "tools\releases.py") `
        (Join-Path $SourceRoot "tools\schema_migrations.py")
    if ($LASTEXITCODE -ne 0) {
        throw "py_compile failed; deployment aborted."
    }
}

$files = Get-ChildItem -LiteralPath $SourceRoot -Recurse -File | Where-Object {
    $relative = Convert-ToRelativePath -Root $SourceRoot -Path $_.FullName
    Test-DeployablePath -RelativePath $relative
}

foreach ($file in $files) {
    $relative = Convert-ToRelativePath -Root $SourceRoot -Path $file.FullName
    $dest = Join-Path $AppTarget $relative
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $dest) | Out-Null
    Copy-Item -LiteralPath $file.FullName -Destination $dest -Force
}

$templates = Get-ChildItem -LiteralPath (Join-Path $SourceRoot "contract_templates") -Filter "*.docx" -File
$copiedTemplates = 0
foreach ($template in $templates) {
    try {
        Copy-Item -LiteralPath $template.FullName -Destination (Join-Path $TemplateTarget $template.Name) -Force
        $copiedTemplates += 1
    } catch {
        Write-DeployLog "Skipped locked contract template: $($template.Name) - $($_.Exception.Message)"
    }
}

$payrollTemplates = Get-ChildItem -LiteralPath (Join-Path $SourceRoot "payroll_templates") -Filter "*.xlsx" -File -ErrorAction SilentlyContinue
$copiedPayrollTemplates = 0
foreach ($template in $payrollTemplates) {
    try {
        Copy-Item -LiteralPath $template.FullName -Destination (Join-Path $PayrollTemplateTarget $template.Name) -Force
        $copiedPayrollTemplates += 1
    } catch {
        Write-DeployLog "Skipped locked payroll template: $($template.Name) - $($_.Exception.Message)"
    }
}

$stalePayrollTemplateNames = @(
    "Payroll PC AD014 - 202605(2).xlsx",
    "Payroll_Monthly_Site_Template.xlsx",
    "Payroll_Management_Template.xlsx",
    "Payroll_Daily_Site_Template.xlsx"
)
foreach ($templateName in $stalePayrollTemplateNames) {
    foreach ($root in @($PayrollTemplateTarget, (Join-Path $AppTarget "payroll_templates"))) {
        $staleTemplate = Join-Path $root $templateName
        if (Test-Path -LiteralPath $staleTemplate) {
            Remove-Item -LiteralPath $staleTemplate -Force
            Write-DeployLog "Removed stale payroll template: $staleTemplate"
        }
    }
}

$operatorScripts = @(
    "mini_pc_restart_hkr_hr_app.bat",
    "mini_pc_upgrade_hkr_hr_v1_and_restart.bat",
    "restart_hkr_hr_app.ps1",
    "setup_system_venv.ps1",
    "start_hkr_hr_app.ps1",
    "stop_hkr_hr_app.ps1",
    "status_hkr_hr_app.ps1",
    "open_hkr_hr_web.bat",
    "allow_hkr_hr_firewall_port.ps1",
    "allow_hkr_hr_firewall_port_admin.bat",
    "init_hkr_hr_database.ps1",
    "mini_pc_init_hkr_hr_database.bat"
)
foreach ($scriptName in $operatorScripts) {
    $scriptPath = Join-Path $SourceRoot "scripts\$scriptName"
    if (Test-Path -LiteralPath $scriptPath) {
        Copy-Item -LiteralPath $scriptPath -Destination (Join-Path $OperatorScriptTarget $scriptName) -Force
    }
}

$rootShortcut = Join-Path $SourceRoot "HKR_HR_Web.url"
if (Test-Path -LiteralPath $rootShortcut) {
    Copy-Item -LiteralPath $rootShortcut -Destination $RootShortcutTarget -Force
    Write-DeployLog "Copied fixed URL shortcut: $RootShortcutTarget"
}

if (Test-Path -LiteralPath $UserGuideSource) {
    Copy-Item -LiteralPath $UserGuideSource -Destination $UserGuideTarget -Force
    Write-DeployLog "Copied HR user guide: $UserGuideTarget"
}

$staleAppScripts = $operatorScripts + @("deploy_to_hkr_hr.ps1")
foreach ($scriptName in $staleAppScripts) {
    $stalePath = Join-Path $AppTarget "scripts\$scriptName"
    if (Test-Path -LiteralPath $stalePath) {
        Remove-Item -LiteralPath $stalePath -Force
        Write-DeployLog "Removed stale app script: $stalePath"
    }
}

$staleAppFiles = @(
    "routes\intake.py",
    "tools\hr_intake.py",
    "templates\intake\index.html",
    "templates\employees\form.html",
    "templates\employees\new_entry.html",
    "templates\employees\generate_contract.html",
    "templates\admin\db.html",
    "templates\employees\attachments.html",
    "templates\employees\certificates.html",
    "templates\employees\export_placeholder.html",
    "templates\employees\phase2_placeholder.html"
)
foreach ($relativePath in $staleAppFiles) {
    $stalePath = Join-Path $AppTarget $relativePath
    if (Test-Path -LiteralPath $stalePath) {
        Remove-Item -LiteralPath $stalePath -Force
        Write-DeployLog "Removed stale app file: $stalePath"
    }
}

$staleAppDirectories = @(
    "_backups",
    "_verification",
    "contract_templates",
    "docs",
    "employee_attachments",
    "payroll_templates",
    "tests"
)
$appTargetFull = [System.IO.Path]::GetFullPath($AppTarget).TrimEnd('\', '/')
foreach ($relativePath in $staleAppDirectories) {
    $stalePath = [System.IO.Path]::GetFullPath((Join-Path $AppTarget $relativePath))
    if (-not $stalePath.StartsWith(
        "$appTargetFull\",
        [System.StringComparison]::OrdinalIgnoreCase
    )) {
        throw "Refusing to remove path outside app target: $stalePath"
    }
    if (Test-Path -LiteralPath $stalePath) {
        Remove-Item -LiteralPath $stalePath -Recurse -Force
        Write-DeployLog "Removed stale app directory: $stalePath"
    }
}

$productionEnv = Join-Path $AppTarget ".env"
if (-not (Test-Path -LiteralPath $productionEnv)) {
    Copy-Item -LiteralPath (Join-Path $SourceRoot ".env.production.example") -Destination $productionEnv
    Write-DeployLog "Created production .env from .env.production.example. Review SECRET_KEY and DATABASE_URL."
} else {
    $envText = Get-Content -Raw -LiteralPath $productionEnv
    if ($envText -match "postgresql\+psycopg2://") {
        $envText = $envText -replace "postgresql\+psycopg2://", "postgresql+psycopg://"
        Set-Content -LiteralPath $productionEnv -Value $envText -NoNewline
        Write-DeployLog "Updated production .env DATABASE_URL from psycopg2 to psycopg."
    }
    $envText = Get-Content -Raw -LiteralPath $productionEnv
    if ($envText -notmatch "(?m)^PAYROLL_TEMPLATE_ROOT=") {
        Add-Content -LiteralPath $productionEnv -Value "`nPAYROLL_TEMPLATE_ROOT=D:\HKR_HR\02.Templates\payroll"
        Write-DeployLog "Added production .env PAYROLL_TEMPLATE_ROOT."
    } elseif ($envText -match "(?m)^PAYROLL_TEMPLATE_ROOT=R:\\02\.Templates\\payroll\s*$") {
        $envText = $envText -replace "(?m)^PAYROLL_TEMPLATE_ROOT=R:\\02\.Templates\\payroll\s*$", "PAYROLL_TEMPLATE_ROOT=D:\HKR_HR\02.Templates\payroll"
        Set-Content -LiteralPath $productionEnv -Value $envText -NoNewline
        Write-DeployLog "Corrected production PAYROLL_TEMPLATE_ROOT to mini PC D: path."
    }
    $runtimeSettings = [ordered]@{
        "ATTENDANCE_BATCH_ROOT" = "D:\HKR_HR\01.Attachments\_attendance_batches"
        "IMPORT_ROOT" = "D:\HKR_HR\01.Attachments\_imports"
        "PAYROLL_OUTPUT_ROOT" = "D:\HKR_HR\03.Output\generated_payroll"
    }
    foreach ($setting in $runtimeSettings.GetEnumerator()) {
        $envText = Get-Content -Raw -LiteralPath $productionEnv
        if ($envText -notmatch "(?m)^$([regex]::Escape($setting.Key))=") {
            Add-Content -LiteralPath $productionEnv -Value "`n$($setting.Key)=$($setting.Value)"
            Write-DeployLog "Added production .env $($setting.Key)."
        }
    }
}

Write-DeployLog "Copied app files: $($files.Count)"
Write-DeployLog "Copied templates: $copiedTemplates / $($templates.Count)"
Write-DeployLog "Copied payroll templates: $copiedPayrollTemplates / $($payrollTemplates.Count)"
Write-DeployLog "Copied operator scripts: $($operatorScripts.Count)"
Write-DeployLog "Done."
Write-DeployLog "Production roots created:"
Write-DeployLog "  $AttachmentRoot"
Write-DeployLog "  $TemplateTarget"
Write-DeployLog "  $PayrollTemplateTarget"
Write-DeployLog "  $GeneratedRoot"
