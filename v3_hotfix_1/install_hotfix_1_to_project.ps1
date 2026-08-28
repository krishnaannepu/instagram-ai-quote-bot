$ErrorActionPreference = "Stop"

$SourceDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $SourceDir

$RequiredProjectFiles = @(
    "main.py",
    "business_knowledge_service.py",
    "quote_service.py",
    "sheets_service.py"
)

foreach ($file in $RequiredProjectFiles) {
    $path = Join-Path $ProjectRoot $file
    if (-not (Test-Path $path)) {
        throw "Required project file is missing: $path"
    }
}

$HotfixFiles = @(
    "business_answer_service_v3.py",
    "conversation_events.py",
    "conversation_state_machine.py",
    "conversation_orchestrator.py",
    "customer_response_renderer_v3.py"
)

foreach ($file in $HotfixFiles) {
    $source = Join-Path $SourceDir $file
    if (-not (Test-Path $source)) {
        throw "Hotfix source file is missing: $source"
    }
}

$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$BackupDir = Join-Path $ProjectRoot "backup-before-v3-hotfix1-$Timestamp"
New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null

Write-Host ""
Write-Host "Project root: $ProjectRoot"
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

Write-Host "Current production files backed up."

foreach ($file in $HotfixFiles) {
    Copy-Item `
        -Path (Join-Path $SourceDir $file) `
        -Destination (Join-Path $ProjectRoot $file) `
        -Force
}

Write-Host "Hotfix files copied to project root."

Push-Location $ProjectRoot
try {
    python -m py_compile `
        business_answer_service_v3.py `
        conversation_events.py `
        conversation_state_machine.py `
        conversation_orchestrator.py `
        customer_response_renderer_v3.py

    if ($LASTEXITCODE -ne 0) {
        throw "Hotfix compile check failed."
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
Write-Host "V3 PRODUCTION HOTFIX 1 ROOT INSTALLATION PASSED"
Write-Host "============================================================"
Write-Host ""
Write-Host "Nothing has been deployed yet."
Write-Host "Backup: $BackupDir"
