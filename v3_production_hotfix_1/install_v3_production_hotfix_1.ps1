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
    "business_answer_service_v3.py"
)

foreach ($file in $ProductionFiles) {
    $existing = Join-Path $ProjectRoot $file

    if (-not (Test-Path $existing)) {
        throw "Expected V3 production file is missing: $existing"
    }

    $source = Join-Path $SourceDir $file

    if (-not (Test-Path $source)) {
        throw "Hotfix source file is missing: $source"
    }
}

$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$BackupDir = Join-Path $ProjectRoot "backup-before-v3-hotfix-$Timestamp"

New-Item `
    -ItemType Directory `
    -Path $BackupDir `
    -Force `
    | Out-Null

Write-Host ""
Write-Host "Project root: $ProjectRoot"
Write-Host "Hotfix backup: $BackupDir"
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

$TempTest = Join-Path $ProjectRoot "test_production_defect_hotfix_v3.py"

Copy-Item `
    -Path (Join-Path $SourceDir "test_production_defect_hotfix_v3.py") `
    -Destination $TempTest `
    -Force

Push-Location $ProjectRoot

try {
    python -m py_compile `
        conversation_events.py `
        conversation_state_machine.py `
        conversation_orchestrator.py `
        business_answer_service_v3.py

    if ($LASTEXITCODE -ne 0) {
        throw "Hotfix compile check failed."
    }

    python test_production_defect_hotfix_v3.py

    if ($LASTEXITCODE -ne 0) {
        throw "Hotfix regression test failed."
    }

    python -c "from main import app; print('V3 HOTFIX MAIN IMPORT PASSED')"

    if ($LASTEXITCODE -ne 0) {
        throw "main.py import failed after hotfix."
    }
}
finally {
    Pop-Location

    if (Test-Path $TempTest) {
        Remove-Item `
            -Path $TempTest `
            -Force
    }
}

Write-Host ""
Write-Host "============================================================"
Write-Host "V3 PRODUCTION HOTFIX 1 INSTALLATION PASSED"
Write-Host "============================================================"
Write-Host ""
Write-Host "Nothing has been deployed yet."
Write-Host "Backup: $BackupDir"
