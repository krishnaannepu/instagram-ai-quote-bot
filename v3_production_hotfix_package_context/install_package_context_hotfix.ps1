param(
    [string]$ProjectRoot = ""
)

$ErrorActionPreference = "Stop"

$SourceDir = Split-Path -Parent $MyInvocation.MyCommand.Path

if ([string]::IsNullOrWhiteSpace($ProjectRoot)) {
    $ProjectRoot = Split-Path -Parent $SourceDir
}

$ProjectRoot = (Resolve-Path $ProjectRoot).Path

$Files = @(
    "conversation_events.py",
    "conversation_state_machine.py",
    "conversation_orchestrator.py",
    "business_question_coordinator_v3.py"
)

$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$BackupDir = Join-Path $ProjectRoot "backup-before-package-context-hotfix-$Timestamp"

New-Item `
    -ItemType Directory `
    -Path $BackupDir `
    -Force `
    | Out-Null

foreach ($file in $Files) {
    $source = Join-Path $SourceDir $file
    $destination = Join-Path $ProjectRoot $file

    if (-not (Test-Path $source)) {
        throw "Hotfix source file missing: $source"
    }

    if (-not (Test-Path $destination)) {
        throw "Production file missing: $destination"
    }

    Copy-Item `
        -Path $destination `
        -Destination (Join-Path $BackupDir $file) `
        -Force
}

Write-Host ""
Write-Host "Backup created: $BackupDir"

foreach ($file in $Files) {
    Copy-Item `
        -Path (Join-Path $SourceDir $file) `
        -Destination (Join-Path $ProjectRoot $file) `
        -Force
}

Push-Location $ProjectRoot

try {
    python -m py_compile `
        conversation_events.py `
        conversation_state_machine.py `
        conversation_orchestrator.py `
        business_question_coordinator_v3.py

    if ($LASTEXITCODE -ne 0) {
        throw "Python compile check failed."
    }

    python -c "from main import app; print('HOTFIX ROOT IMPORT PASSED')"

    if ($LASTEXITCODE -ne 0) {
        throw "Root import check failed."
    }
}
finally {
    Pop-Location
}

Write-Host ""
Write-Host "============================================================"
Write-Host "V3 PACKAGE CONTEXT HOTFIX INSTALLATION PASSED"
Write-Host "============================================================"
Write-Host ""
Write-Host "Nothing has been deployed to Cloud Run."
Write-Host "Backup: $BackupDir"
