# V3 Block 11 — Final Hard Cutover

Block 11 is the final core V3 block.

It removes conversation control from the production FastAPI controller and
makes the POST Instagram webhook delegate to the V3 channel/runtime.

## Final production controller

```text
Meta POST /instagram/webhook
        ↓
main.py
        ↓
InstagramChannelAdapterV3
        ↓
LocalConversationRuntimeV3
        ↓
ConversationOrchestrator
        ↓
one authoritative state machine
```

`main.py` no longer contains quote, package, travel, pricing, email, handoff,
or callback routing.

## Preserved public endpoints

- GET /
- GET /privacy-policy
- GET /terms
- GET /data-deletion
- GET /instagram/webhook
- GET /instagram/callback
- POST /instagram/webhook

## Final additions

Block 11 adds:

- explicit first-message greeting/welcome behavior;
- Get a Quote / Speak to Team welcome buttons;
- outgoing Instagram business-sender filtering;
- explicit Meta echo filtering;
- in-memory duplicate message-id protection;
- lazy V3 runtime initialization;
- clean production `main.py`;
- safe root installer with automatic backup.

## Step 1 — Validate inside v3_foundation

Extract this ZIP over your current `v3_foundation`.

Run:

```powershell
python test_all_v3_offline.py
```

Then run the live Gemini entry check:

```powershell
python test_live_block11_entry_semantics_v3.py
```

Expected:

```text
V3 BLOCK 11 LIVE ENTRY SEMANTIC TEST PASSED
```

## Step 2 — Install V3 into project root

From inside:

```text
C:\Users\krishna\Documents\instagram-ai-quote-bot\v3_foundation
```

run:

```powershell
powershell -ExecutionPolicy Bypass -File .\install_block11_to_project.ps1
```

The installer:

1. verifies your existing service modules exist;
2. creates a timestamped backup folder in project root;
3. backs up the existing `main.py` and matching V3 files;
4. copies only V3 production files to project root;
5. compiles the production modules;
6. imports the new `main.py`;
7. does NOT deploy anything.

Expected:

```text
V3 BLOCK 11 ROOT INSTALLATION PASSED
```

## Step 3 — Root preflight

Move to project root:

```powershell
cd "C:\Users\krishna\Documents\instagram-ai-quote-bot"
```

Run:

```powershell
python -c "from main import app; print('V3 ROOT MAIN IMPORT PASSED')"
```

Optionally start the API locally:

```powershell
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Visit the health endpoint and confirm it reports:

```json
{
  "status": "running",
  "service": "Instagram Sales Automation API",
  "conversation_engine": "v3"
}
```

Stop Uvicorn before deploying.

## Step 4 — Cloud Run deployment

Before deployment, capture the existing service configuration:

```powershell
gcloud run services describe instagram-ai-quote-bot --region europe-west2 --project gen-lang-client-0149798839 --format=export > cloudrun-before-v3.yaml
```

Deploy the existing project root:

```powershell
gcloud run deploy instagram-ai-quote-bot --source . --region europe-west2 --project gen-lang-client-0149798839 --allow-unauthenticated
```

Then inspect the serving revision:

```powershell
gcloud run services describe instagram-ai-quote-bot --region europe-west2 --project gen-lang-client-0149798839 --format="value(status.latestReadyRevisionName,status.url)"
```

Do not delete the timestamped local backup until real Instagram validation is
complete.

## Post-deployment acceptance conversation

Validate at least:

```text
Hi
→ welcome buttons

Get a Quote
→ Wedding
→ Basic
→ ask package/price difference
→ answer comparison
→ keep/switch prompt
→ switch Premium
→ Both
→ No travel
→ 8 hours
→ date
→ Birmingham
→ deterministic quote

Then verify:
→ email Yes path
→ email No path
→ Speak to Team
→ Request Callback
→ invalid phone
→ valid phone
→ callback preference
→ duplicate callback protection
→ Start New Quote
→ Finish
```

## Important remaining hardening

V3 currently uses an in-memory session repository and in-memory message
deduplication.

That is acceptable for the controlled MVP cutover, but Cloud Run
restart/scaling can lose active session state. The next production-hardening
phase should replace the in-memory repository with Firestore and persistent
message-id deduplication.

That hardening is separate from the 11-block conversation architecture rebuild.
