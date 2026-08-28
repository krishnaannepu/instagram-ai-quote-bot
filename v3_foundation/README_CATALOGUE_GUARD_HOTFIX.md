# V3 production hotfix — strict catalogue/domain guard

This is not a new architecture block.

It fixes the production defect:

```text
State: QUOTE_PACKAGE
Service: Wedding
Bot asks: Basic or Premium?
Customer types: Wedding
Old result: incorrectly advances to coverage
Correct result: stay on package and ask Basic or Premium again
```

## What changed

Gemini still interprets natural language, but before any enumerated quote value
can enter the state machine, Python now checks it against the authoritative
allowed values for the current state.

Examples:

- QUOTE_SERVICE: only current supported services are valid.
- QUOTE_PACKAGE: only packages configured for the selected service are valid.
- QUOTE_COVERAGE: only Photography / Videography / Both are valid.
- QUOTE_TRAVEL: only Yes / No are valid.
- package switching is also validated against the selected service catalogue.

An invalid value creates `INVALID_FIELD_VALUE`. It never mutates quote state
and never advances the state machine.

## Run before installation

From `v3_foundation`:

```powershell
python test_hotfix_catalogue_guard_v3.py
python test_live_hotfix_catalogue_guard_v3.py
```

Expected:

```text
V3 PRODUCTION HOTFIX CATALOGUE GUARD TEST PASSED
V3 LIVE CATALOGUE GUARD HOTFIX TEST PASSED
```

## Install to project root

```powershell
powershell -ExecutionPolicy Bypass -File .\install_catalogue_guard_hotfix.ps1
```

Expected:

```text
V3 CATALOGUE GUARD HOTFIX INSTALLATION PASSED
```

The installer backs up only the three modified production files and does not
deploy.

Then deploy the normal project root to Cloud Run.
