# Production defect fix

This package fixes the exact Instagram behavior captured in the production
screenshot.

## Defect 1

At `QUOTE_PACKAGE`, Gemini could return:

```text
field_name = package
value = Wedding
```

The old V3 contract validated the field name but not the value against the
Python catalogue.

The fix adds a Python catalogue/domain guard. For enumerated fields, a value
must exist in the authoritative allowed values before the state machine can
apply it.

For Wedding package selection:

```text
allowed = Basic, Premium
Wedding -> rejected
state remains QUOTE_PACKAGE
package remains None
```

## Defect 2

When Wedding was already known and the customer asked:

```text
What's the difference between basic and premium
```

the answer could still be generic and ask which service was intended.

The fix routes package comparison/package-info questions with a known service
through deterministic approved Sheets facts. Gemini no longer generates these
package facts.

## Exact screenshot regression

Run:

```powershell
python test_production_screenshot_regression_v3.py
```

Expected:

```text
PASS 1 - Wedding remains the selected service at package state
PASS 2 - Basic/Premium question uses exact Wedding Sheets facts and returns to package selection
PASS 3 - Wedding is rejected by Python as a package and state does not advance
PASS 4 - Basic is accepted and coverage becomes authoritative
PASS 5 - comparison after Basic selection answers exact facts before keep/switch

V3 PRODUCTION SCREENSHOT REGRESSION TEST PASSED
```

## Install

From inside the extracted hotfix folder:

```powershell
powershell -ExecutionPolicy Bypass -File .\install_production_defect_fix.ps1 -ProjectRoot "C:\Users\krishna\Documents\instagram-ai-quote-bot"
```

The installer backs up the five modified production files, copies the fix,
compiles them, runs the exact screenshot regression, and imports production
`main.py`.

It does not deploy.
