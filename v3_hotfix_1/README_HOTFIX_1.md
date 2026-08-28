# V3 Production Hotfix 1

This is **not another architecture block**. It fixes the two production defects
seen in the Instagram acceptance screenshot after V3 Block 11 deployment.

## Defect 1 — Wrong enum value corrupted state

When V3 was waiting for a package (`Basic` or `Premium`), the text `Wedding`
could be accepted as the package and the state could advance to coverage.

### Fix

Python now owns a strict catalogue/domain guard:

- service must be one of the live supported services;
- package must be one of the packages for the selected service;
- coverage must be Photography / Videography / Both;
- travel must be Yes / No;
- exact values from another domain are rejected **before Gemini**;
- even if Gemini proposes an invalid enum value, Python rejects it;
- rejection never mutates quote state and never advances the state machine.

## Defect 2 — Generic package comparison despite known service

With `Wedding` already in state, asking:

```text
What's the difference between basic and premium
```

could produce a generic Gemini answer asking which service the customer wanted.

### Fix

When the service is already known and the customer is comparing package options,
V3 now builds the comparison deterministically from the approved Google Sheets
`Pricing` and `Packages` rows. Gemini is not allowed to replace that answer with
a generic one.

The comparison works both:

- before a package has been selected; and
- after a package has been selected, before the keep/switch reconfirmation.

## Files changed

Only four production modules are replaced:

- `conversation_events.py`
- `conversation_state_machine.py`
- `conversation_orchestrator.py`
- `business_question_coordinator_v3.py`

## Validate before installation

From `v3_hotfix_1`:

```powershell
python test_hotfix_1_regression.py
python test_live_hotfix_1.py
```

The first is fully offline. The second uses real Gemini + real Google Sheets but
does not send Instagram messages or email.

Expected:

```text
V3 PRODUCTION HOTFIX 1 REGRESSION PASSED
V3 PRODUCTION HOTFIX 1 LIVE TEST PASSED
```

## Install into project root

```powershell
powershell -ExecutionPolicy Bypass -File .\install_hotfix_1.ps1
```

The installer first reruns the focused regression, then creates a timestamped
backup, copies only the four changed production files, compiles them, and imports
`main.py`. It does **not** deploy Cloud Run.

Expected:

```text
V3 PRODUCTION HOTFIX 1 ROOT INSTALLATION PASSED
```

## Deploy after local validation

From project root:

```powershell
gcloud run deploy instagram-ai-quote-bot --source . --region europe-west2 --project gen-lang-client-0149798839 --allow-unauthenticated
```

Then verify the latest revision before retesting Instagram.
