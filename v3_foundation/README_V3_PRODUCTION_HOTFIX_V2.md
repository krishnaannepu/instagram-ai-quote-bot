# V3 Production Hotfix V2

This is a focused production defect fix, not another architecture block.

## Defect 1 — wrong-domain values could advance state

Observed live:

```text
State: QUOTE_PACKAGE
Customer: Wedding
Gemini: UNCLEAR
Old result: package deferred -> QUOTE_COVERAGE
```

New rule:

```text
Gemini interprets language.
Python owns catalogue/domain validity.
```

A known value from the wrong quote domain is rejected as
`INVALID_FIELD_VALUE`; the state remains unchanged.

## Defect 2 — package comparison ignored selected service

Observed live:

```text
service = Wedding
customer asks Basic vs Premium
answer asks which service the customer wants
```

New rule:

- business knowledge is scoped to the already-selected service;
- package comparison/pricing is generated from approved Google Sheets pricing
  rows for that service;
- the answer cannot ask for the service again;
- the flow resumes the exact package-selection state.

## Run inside v3_foundation

```powershell
python test_hotfix_v2_state_safety.py
python test_hotfix_v2_package_comparison.py
python test_all_v3_offline.py
python test_live_hotfix_v2_production_paths.py
```

Do not install or deploy unless all four pass.

## Install into project root

```powershell
powershell -ExecutionPolicy Bypass -File .\install_hotfix_v2_to_project.ps1
```

The installer backs up only the five patched production files and does not
deploy Cloud Run.
