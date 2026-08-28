param(
    [string]$ProjectRoot = ""
)

$ErrorActionPreference = "Stop"

$SourceDir = Split-Path -Parent $MyInvocation.MyCommand.Path

if ([string]::IsNullOrWhiteSpace($ProjectRoot)) {
    $ProjectRoot = Split-Path -Parent $SourceDir
}

$ProjectRoot = (Resolve-Path $ProjectRoot).Path

$RequiredRootFiles = @(
    "main.py",
    "conversation_orchestrator.py",
    "conversation_state_machine.py",
    "conversation_events.py",
    "business_question_coordinator_v3.py",
    "business_answer_service_v3.py",
    "business_knowledge_adapter_v3.py"
)

foreach ($file in $RequiredRootFiles) {
    $path = Join-Path $ProjectRoot $file

    if (-not (Test-Path $path)) {
        throw "Required V3 project file is missing: $path"
    }
}

$ChangedProductionFiles = @(
    "conversation_events.py",
    "conversation_state_machine.py",
    "conversation_orchestrator.py",
    "business_question_coordinator_v3.py"
)

foreach ($file in $ChangedProductionFiles) {
    $source = Join-Path $SourceDir $file

    if (-not (Test-Path $source)) {
        throw "Hotfix source file is missing: $source"
    }
}

$FocusedTest = Join-Path $SourceDir "test_hotfix_1_regression.py"

if (-not (Test-Path $FocusedTest)) {
    throw "Focused hotfix test is missing: $FocusedTest"
}

Write-Host ""
Write-Host "Running Hotfix 1 regression before changing project root..."
Write-Host ""

Push-Location $SourceDir
try {
    python test_hotfix_1_regression.py

    if ($LASTEXITCODE -ne 0) {
        throw "Hotfix regression failed. No project files were changed."
    }
}
finally {
    Pop-Location
}

$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$BackupDir = Join-Path $ProjectRoot "backup-before-v3-hotfix1-$Timestamp"

New-Item `
    -ItemType Directory `
    -Path $BackupDir `
    -Force `
    | Out-Null

Write-Host ""
Write-Host "Project root: $ProjectRoot"
Write-Host "Backup folder: $BackupDir"
Write-Host ""

foreach ($file in $ChangedProductionFiles) {
    Copy-Item `
        -Path (Join-Path $ProjectRoot $file) `
        -Destination (Join-Path $BackupDir $file) `
        -Force
}

Write-Host "Current production files backed up."

foreach ($file in $ChangedProductionFiles) {
    Copy-Item `
        -Path (Join-Path $SourceDir $file) `
        -Destination (Join-Path $ProjectRoot $file) `
        -Force
}

Write-Host "Hotfix files copied to project root."
Write-Host ""

Push-Location $ProjectRoot
try {
    python -m py_compile `
        conversation_events.py `
        conversation_state_machine.py `
        conversation_orchestrator.py `
        business_question_coordinator_v3.py `
        main.py

    if ($LASTEXITCODE -ne 0) {
        throw "Python compile check failed after hotfix copy."
    }

    python -c "from main import app; print('V3 HOTFIX 1 ROOT MAIN IMPORT PASSED')"

    if ($LASTEXITCODE -ne 0) {
        throw "main.py import check failed after hotfix copy."
    }
}
finally {
    Pop-Location
}

Write-Host ""
Write-Host "============================================================"
Write-Host "V3 PRODUCTION HOTFIX 1 ROOT INSTALLATION PASSED"
Write-Host "============================================================"
Write-Host ""
Write-Host "Nothing has been deployed to Cloud Run yet."
Write-Host "Backup: $BackupDir"
