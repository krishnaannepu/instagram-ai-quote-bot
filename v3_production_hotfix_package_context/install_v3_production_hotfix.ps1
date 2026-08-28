param(
    [string]$ProjectRoot = ""
)

$ErrorActionPreference = "Stop"

$SourceDir = Split-Path -Parent $MyInvocation.MyCommand.Path

if ([string]::IsNullOrWhiteSpace($ProjectRoot)) {
    $ProjectRoot = Split-Path -Parent $SourceDir
}

$ProjectRoot = (Resolve-Path $ProjectRoot).Path

$ProductionFiles = @(
    "conversation_events.py",
    "conversation_state_machine.py",
    "conversation_orchestrator.py",
    "business_answer_service_v3.py",
    "business_question_coordinator_v3.py",
    "customer_response_renderer_v3.py"
)

foreach ($file in $ProductionFiles) {
    $source = Join-Path $SourceDir $file
    if (-not (Test-Path $source)) {
        throw "Hotfix source file is missing: $source"
    }

    $destination = Join-Path $ProjectRoot $file
    if (-not (Test-Path $destination)) {
        throw "Current V3 production file is missing: $destination"
    }
}

$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$BackupDir = Join-Path $ProjectRoot "backup-before-v3-package-hotfix-$Timestamp"
New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null

Write-Host ""
Write-Host "Project root: $ProjectRoot"
Write-Host "Backup folder: $BackupDir"
Write-Host ""

foreach ($file in $ProductionFiles) {
    Copy-Item `
        -Path (Join-Path $ProjectRoot $file) `
        -Destination (Join-Path $BackupDir $file) `
        -Force
}

Write-Host "Current production V3 files backed up."

foreach ($file in $ProductionFiles) {
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
        business_answer_service_v3.py `
        business_question_coordinator_v3.py `
        customer_response_renderer_v3.py

    if ($LASTEXITCODE -ne 0) {
        throw "Python compile check failed."
    }

    python -c "from main import app; print('V3 HOTFIX ROOT MAIN IMPORT PASSED')"

    if ($LASTEXITCODE -ne 0) {
        throw "Root main import failed after hotfix."
    }
}
finally {
    Pop-Location
}

Write-Host ""
Write-Host "============================================================"
Write-Host "V3 PRODUCTION PACKAGE-CONTEXT HOTFIX INSTALLED"
Write-Host "============================================================"
Write-Host ""
Write-Host "Nothing has been deployed to Cloud Run yet."
Write-Host "Backup: $BackupDir"
