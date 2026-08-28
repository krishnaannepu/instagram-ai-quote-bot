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
    "customer_response_renderer_v3.py",
    "business_question_coordinator_v3.py"
)

$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$BackupDir = Join-Path $ProjectRoot "backup-before-production-hotfix-$Timestamp"

New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null

foreach ($file in $Files) {
    $destination = Join-Path $ProjectRoot $file

    if (Test-Path $destination) {
        Copy-Item `
            -Path $destination `
            -Destination (Join-Path $BackupDir $file) `
            -Force
    }

    Copy-Item `
        -Path (Join-Path $SourceDir $file) `
        -Destination $destination `
        -Force
}

Copy-Item `
    -Path (Join-Path $SourceDir "test_production_screenshot_regression_v3.py") `
    -Destination (Join-Path $ProjectRoot "test_production_screenshot_regression_v3.py") `
    -Force

Push-Location $ProjectRoot

try {
    python -m py_compile `
        conversation_events.py `
        conversation_state_machine.py `
        conversation_orchestrator.py `
        customer_response_renderer_v3.py `
        business_question_coordinator_v3.py `
        test_production_screenshot_regression_v3.py

    if ($LASTEXITCODE -ne 0) {
        throw "Python compile check failed."
    }

    python test_production_screenshot_regression_v3.py

    if ($LASTEXITCODE -ne 0) {
        throw "Production screenshot regression failed."
    }

    python -c "from main import app; print('PRODUCTION MAIN IMPORT PASSED')"

    if ($LASTEXITCODE -ne 0) {
        throw "Production main import failed."
    }
}
finally {
    Pop-Location
}

Write-Host ""
Write-Host "============================================================"
Write-Host "V3 PRODUCTION DEFECT FIX INSTALLED"
Write-Host "============================================================"
Write-Host "Backup: $BackupDir"
Write-Host "Nothing has been deployed yet."
