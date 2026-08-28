param(
    [string]$ProjectRoot = ""
)

$ErrorActionPreference = "Stop"

$SourceDir = Split-Path -Parent $MyInvocation.MyCommand.Path

if ([string]::IsNullOrWhiteSpace($ProjectRoot)) {
    $ProjectRoot = Split-Path -Parent $SourceDir
}

$ProjectRoot = (Resolve-Path $ProjectRoot).Path

$PatchFiles = @(
    "conversation_events.py",
    "conversation_state_machine.py",
    "conversation_orchestrator.py",
    "business_answer_service_v3.py",
    "business_question_coordinator_v3.py"
)

$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$BackupDir = Join-Path $ProjectRoot "backup-before-v3-hotfix-v2-$Timestamp"

New-Item `
    -ItemType Directory `
    -Path $BackupDir `
    -Force `
    | Out-Null

Write-Host ""
Write-Host "Project root: $ProjectRoot"
Write-Host "Hotfix backup: $BackupDir"
Write-Host ""

foreach ($file in $PatchFiles) {
    $source = Join-Path $SourceDir $file
    $destination = Join-Path $ProjectRoot $file

    if (-not (Test-Path $source)) {
        throw "Hotfix source file is missing: $source"
    }

    if (-not (Test-Path $destination)) {
        throw "Production target file is missing: $destination"
    }

    Copy-Item `
        -Path $destination `
        -Destination (Join-Path $BackupDir $file) `
        -Force
}

Write-Host "Current production files backed up."

foreach ($file in $PatchFiles) {
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
        business_question_coordinator_v3.py

    if ($LASTEXITCODE -ne 0) {
        throw "Python compile check failed."
    }

    python -c "from main import app; print('HOTFIX V2 ROOT MAIN IMPORT PASSED')"

    if ($LASTEXITCODE -ne 0) {
        throw "main.py import check failed."
    }
}
finally {
    Pop-Location
}

Write-Host ""
Write-Host "============================================================"
Write-Host "V3 PRODUCTION HOTFIX V2 ROOT INSTALLATION PASSED"
Write-Host "============================================================"
Write-Host ""
Write-Host "Nothing has been deployed to Cloud Run yet."
Write-Host "Backup: $BackupDir"
