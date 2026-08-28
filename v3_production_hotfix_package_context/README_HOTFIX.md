# V3 Production Hotfix — Package Context v2

This is a complete self-contained hotfix package.

It fixes the two defects found during the first real Instagram acceptance test:

1. A service value such as `Wedding` can no longer be accepted when the
   authoritative state expects package `Basic` or `Premium`.
2. When the service is already known, a Basic/Premium package question is
   answered deterministically from that service's approved Google Sheets
   pricing instead of allowing a generic Gemini response to ask for the
   service again.

## Test first

Inside this extracted folder:

```powershell
python test_v3_production_hotfix_package_context.py
```

Expected:

```text
PASS 1 - Wedding cannot be accepted as a package
PASS 2 - valid Basic package advances and is canonicalized
PASS 3 - Wedding package comparison is deterministic and service-aware
PASS 4 - selected package is preserved while exact comparison is answered

V3 PRODUCTION HOTFIX PACKAGE CONTEXT TEST PASSED
```

## Install into project root

Only after the test passes:

```powershell
powershell -ExecutionPolicy Bypass -File .\install_package_context_hotfix.ps1
```

The installer backs up and replaces only:

- `conversation_events.py`
- `conversation_state_machine.py`
- `conversation_orchestrator.py`
- `business_question_coordinator_v3.py`

It does not deploy anything.

## Deploy

After installation succeeds, move to project root and deploy normally:

```powershell
cd "C:\Users\krishna\Documents\instagram-ai-quote-bot"

gcloud run deploy instagram-ai-quote-bot --source . --region europe-west2 --project gen-lang-client-0149798839 --allow-unauthenticated
```
