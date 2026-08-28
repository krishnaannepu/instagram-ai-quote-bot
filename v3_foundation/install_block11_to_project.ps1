param(
    [string]$ProjectRoot = ""
)

$ErrorActionPreference = "Stop"

$SourceDir = Split-Path -Parent $MyInvocation.MyCommand.Path

if ([string]::IsNullOrWhiteSpace($ProjectRoot)) {
    $ProjectRoot = Split-Path -Parent $SourceDir
}

$ProjectRoot = (Resolve-Path $ProjectRoot).Path

$RequiredExistingFiles = @(
    "business_knowledge_service.py",
    "quote_service.py",
    "sheets_service.py",
    "instagram_service.py",
    "email_service.py"
)

foreach ($file in $RequiredExistingFiles) {
    $path = Join-Path $ProjectRoot $file

    if (-not (Test-Path $path)) {
        throw "Required existing project file is missing: $path"
    }
}

$ProductionFiles = @(
    "main.py",
    "business_answer_service_v3.py",
    "business_knowledge_adapter_v3.py",
    "business_question_coordinator_v3.py",
    "conversation_events.py",
    "conversation_models.py",
    "conversation_orchestrator.py",
    "conversation_state_machine.py",
    "customer_response_renderer_v3.py",
    "email_delivery_adapter_v3.py",
    "event_normalizer.py",
    "gemini_semantic_adapter.py",
    "handoff_callback_service_v3.py",
    "instagram_channel_adapter_v3.py",
    "instagram_sender_v3.py",
    "lead_persistence_adapter_v3.py",
    "local_conversation_runtime_v3.py",
    "meta_webhook_parser_v3.py",
    "quote_adapter_v3.py",
    "quote_completion_service_v3.py",
    "response_plan.py",
    "semantic_contract.py",
    "session_repository_v3.py",
    "turn_logger.py",
    "v3_runtime_factory.py"
)

foreach ($file in $ProductionFiles) {
    $source = Join-Path $SourceDir $file

    if (-not (Test-Path $source)) {
        throw "Block 11 source file is missing: $source"
    }
}

$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$BackupDir = Join-Path $ProjectRoot "backup-before-v3-$Timestamp"

New-Item `
    -ItemType Directory `
    -Path $BackupDir `
    -Force `
    | Out-Null

Write-Host ""
Write-Host "Project root: $ProjectRoot"
Write-Host "Backup folder: $BackupDir"
Write-Host ""

foreach ($file in $ProductionFiles) {
    $destination = Join-Path $ProjectRoot $file

    if (Test-Path $destination) {
        Copy-Item `
            -Path $destination `
            -Destination (Join-Path $BackupDir $file) `
            -Force
    }
}

Write-Host "Existing matching files backed up."

foreach ($file in $ProductionFiles) {
    Copy-Item `
        -Path (Join-Path $SourceDir $file) `
        -Destination (Join-Path $ProjectRoot $file) `
        -Force
}

Write-Host "V3 production files copied to project root."
Write-Host ""

Push-Location $ProjectRoot

try {
    python -m py_compile `
        main.py `
        business_answer_service_v3.py `
        business_knowledge_adapter_v3.py `
        business_question_coordinator_v3.py `
        conversation_events.py `
        conversation_models.py `
        conversation_orchestrator.py `
        conversation_state_machine.py `
        customer_response_renderer_v3.py `
        email_delivery_adapter_v3.py `
        event_normalizer.py `
        gemini_semantic_adapter.py `
        handoff_callback_service_v3.py `
        instagram_channel_adapter_v3.py `
        instagram_sender_v3.py `
        lead_persistence_adapter_v3.py `
        local_conversation_runtime_v3.py `
        meta_webhook_parser_v3.py `
        quote_adapter_v3.py `
        quote_completion_service_v3.py `
        response_plan.py `
        semantic_contract.py `
        session_repository_v3.py `
        turn_logger.py `
        v3_runtime_factory.py

    if ($LASTEXITCODE -ne 0) {
        throw "Python compile check failed."
    }

    python -c "from main import app; print('V3 ROOT MAIN IMPORT PASSED')"

    if ($LASTEXITCODE -ne 0) {
        throw "main.py import check failed."
    }
}
finally {
    Pop-Location
}

Write-Host ""
Write-Host "============================================================"
Write-Host "V3 BLOCK 11 ROOT INSTALLATION PASSED"
Write-Host "============================================================"
Write-Host ""
Write-Host "Nothing has been deployed to Cloud Run yet."
Write-Host "Backup: $BackupDir"
