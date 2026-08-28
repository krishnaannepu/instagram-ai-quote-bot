# V3 Production Hotfix 1

This is not another architecture block.

It fixes the two concrete production defects visible in the Instagram
acceptance conversation.

## Fix 1 — invalid package cannot advance state

At `QUOTE_PACKAGE`, only the current service's approved packages are valid.

If Gemini interprets:

```text
field = package
value = Wedding
```

Python now rejects it before state mutation:

```text
INVALID_FIELD_VALUE
→ state remains QUOTE_PACKAGE
→ package remains empty
→ Basic / Premium are asked again
```

## Fix 2 — package comparison uses the already-selected service

If `service = Wedding` and the customer asks Basic vs Premium, V3 now builds
the package/pricing answer directly from Wedding Pricing rows.

It cannot ask which service the customer wants and Birthday/Portrait/Event
pricing cannot leak into the answer.

## Included regression

```text
PASS 1 - Wedding cannot be accepted as a package or advance to coverage
PASS 2 - Wedding package comparison is answered from Wedding Sheets rows
PASS 3 - package comparison is scoped to the already-selected service
```

## Install

Extract this ZIP as:

```text
C:\Users\krishna\Documents\instagram-ai-quote-bot\v3_hotfix_1
```

From inside that folder run:

```powershell
powershell -ExecutionPolicy Bypass -File .\install_v3_production_hotfix_1.ps1
```

The installer backs up the four current production V3 files, copies the
hotfix, compiles them, runs the focused regression from project root, imports
`main.py`, and does not deploy Cloud Run.
