# V3 Production Hotfix 1 — Package Domain Guard + Service-Grounded Comparison

This is **not another architecture block**. It fixes the two production defects
shown in the Instagram screenshot after Block 11 deployment.

## Defect 1 — invalid package value advanced state

Observed:

```text
State: QUOTE_PACKAGE
Customer: Wedding
Bad semantic output: FIELD_VALUE(package=Wedding)
Old behavior: package became Wedding and flow advanced to coverage
```

Fix:

```text
Gemini interpretation
    ↓
Python catalogue guard
    ↓
Allowed packages for Wedding = [Basic, Premium]
    ↓
Wedding rejected
    ↓
QUOTE_PACKAGE remains unchanged
```

The same Python domain guard now protects enumerated service, package,
coverage, travel, quote-change, and package-switch values.

## Defect 2 — package comparison forgot selected Wedding service

Observed:

```text
Wedding already selected
Customer: What's the difference between Basic and Premium?
Old answer: Which service are you interested in?
```

Fix:

Core Basic-vs-Premium comparisons are now built deterministically from the
approved Pricing rows for the already-selected service.

For other business questions, Gemini receives only Pricing/Package rows for
the selected service and is explicitly forbidden from asking for that service
again.

## Files changed

- business_answer_service_v3.py
- conversation_events.py
- conversation_state_machine.py
- conversation_orchestrator.py
- customer_response_renderer_v3.py

## Validate in v3_foundation

```powershell
python test_hotfix_screenshot_regression_v3.py
python test_live_hotfix_real_wedding_v3.py
python test_all_v3_offline.py
```

Then install into project root:

```powershell
powershell -ExecutionPolicy Bypass -File .\install_hotfix_1_to_project.ps1
```

The installer backs up the five current production files and does **not**
deploy Cloud Run.
