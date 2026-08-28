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
    "conversation_orchestrator.py"
)

foreach ($file in $Files) {
    $source = Join-Path $SourceDir $file
    $destination = Join-Path $ProjectRoot $file

    if (-not (Test-Path $source)) {
        throw "Hotfix source is missing: $source"
    }

    if (-not (Test-Path $destination)) {
        throw "Existing V3 project file is missing: $destination"
    }
}

$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$BackupDir = Join-Path $ProjectRoot "backup-before-catalogue-guard-hotfix-$Timestamp"
New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null

foreach ($file in $Files) {
    Copy-Item `
        -Path (Join-Path $ProjectRoot $file) `
        -Destination (Join-Path $BackupDir $file) `
        -Force
}

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
        conversation_orchestrator.py

    if ($LASTEXITCODE -ne 0) {
        throw "Hotfix compile check failed."
    }

    python -c "from conversation_orchestrator import ConversationOrchestrator; print('CATALOGUE GUARD ROOT IMPORT PASSED')"

    if ($LASTEXITCODE -ne 0) {
        throw "Hotfix import check failed."
    }
}
finally {
    Pop-Location
}

Write-Host ""
Write-Host "============================================================"
Write-Host "V3 CATALOGUE GUARD HOTFIX INSTALLATION PASSED"
Write-Host "============================================================"
Write-Host "Backup: $BackupDir"
Write-Host "Nothing has been deployed yet."
