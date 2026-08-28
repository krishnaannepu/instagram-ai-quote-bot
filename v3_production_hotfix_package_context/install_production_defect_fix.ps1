param(
    [string]$ProjectRoot = ""
)

$ErrorActionPreference = "Stop"

$SourceDir = Split-Path -Parent $MyInvocation.MyCommand.Path

if ([string]::IsNullOrWhiteSpace($ProjectRoot)) {
    $ProjectRoot = Split-Path -Parent $SourceDir
}

$ProjectRoot = (Resolve-Path $ProjectRoot).Path

Write-Host ""
Write-Host "Production project root: $ProjectRoot"
Write-Host "Hotfix source folder: $SourceDir"
Write-Host ""

$HotfixFiles = @(
    "conversation_events.py",
    "conversation_state_machine.py",
    "conversation_orchestrator.py",
    "business_question_coordinator_v3.py",
    "business_answer_service_v3.py",
    "gemini_semantic_adapter.py"
)

foreach ($file in $HotfixFiles) {
    $source = Join-Path $SourceDir $file

    if (-not (Test-Path $source)) {
        throw "Required hotfix file is missing: $source"
    }
}

$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$BackupDir = Join-Path $ProjectRoot "backup-before-production-hotfix-$Timestamp"

New-Item `
    -ItemType Directory `
    -Path $BackupDir `
    -Force |
    Out-Null

Write-Host "Backup folder: $BackupDir"
Write-Host ""

foreach ($file in $HotfixFiles) {
    $destination = Join-Path $ProjectRoot $file

    if (Test-Path $destination) {
        Copy-Item `
            -Path $destination `
            -Destination (Join-Path $BackupDir $file) `
            -Force
    }
}

Write-Host "Existing production files backed up."

foreach ($file in $HotfixFiles) {
    Copy-Item `
        -Path (Join-Path $SourceDir $file) `
        -Destination (Join-Path $ProjectRoot $file) `
        -Force
}

Write-Host "Hotfix files copied to production project root."
Write-Host ""

Push-Location $ProjectRoot

try {
    python -m py_compile `
        conversation_events.py `
        conversation_state_machine.py `
        conversation_orchestrator.py `
        business_question_coordinator_v3.py `
        business_answer_service_v3.py `
        gemini_semantic_adapter.py

    if ($LASTEXITCODE -ne 0) {
        throw "Python compile validation failed."
    }

    python -c "from main import app; print('PRODUCTION MAIN IMPORT PASSED')"

    if ($LASTEXITCODE -ne 0) {
        throw "Production main.py import validation failed."
    }
}
finally {
    Pop-Location
}

Write-Host ""
Write-Host "========================================================================"
Write-Host "V3 PRODUCTION DEFECT FIX INSTALLATION PASSED"
Write-Host "========================================================================"
Write-Host ""
Write-Host "Nothing has been deployed to Cloud Run yet."
Write-Host "Backup: $BackupDir"