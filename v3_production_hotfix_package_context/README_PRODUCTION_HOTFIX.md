# V3 Production Hotfix — Package Context + Strict Catalogue Validation

This is **not Block 12**. It is a focused production defect fix after real
Instagram acceptance exposed two missing contracts.

## Defect 1 — invalid package value could advance the quote

Observed:

```text
Expected field: package
Customer/Gemini value: Wedding
Old result: package = Wedding → advanced to coverage
```

Fixed:

```text
Gemini interprets meaning
→ Python checks value against [Basic, Premium]
→ Wedding is rejected
→ package remains empty
→ state remains QUOTE_PACKAGE
→ Basic/Premium is asked again
```

The same Python catalogue guard applies to enumerated service, package,
coverage and travel selections, plus package switching.

## Defect 2 — package-question context was lost after an IDLE business answer

Observed:

```text
Customer: wedding-specific Basic/Premium difference with prices
Bot: correct Wedding information
Bot: Hi! How can we help you today?
Customer: okay do basic
Bot: unknown information / reset
```

Fixed:

```text
Wedding-specific package question from IDLE
→ exact Wedding rows from Sheets
→ service Wedding is preserved
→ state becomes QUOTE_PACKAGE
→ asks Basic or Premium
→ acknowledgement keeps state
→ "okay do basic" → Basic → QUOTE_COVERAGE
```

Package comparisons with a known service are now constructed from the
service-filtered approved Pricing rows rather than allowing a generic package
answer.

## Files changed

- `conversation_events.py`
- `conversation_state_machine.py`
- `conversation_orchestrator.py`
- `business_answer_service_v3.py`
- `business_question_coordinator_v3.py`
- `customer_response_renderer_v3.py`

## Validate before installing

From the extracted hotfix folder:

```powershell
python test_v3_production_hotfix_package_context.py
python test_live_production_hotfix_v3.py
```

The first test is fully offline and reproduces both production failures.

The second uses real Gemini + real Google Sheets but sends no Instagram
message and no email.

## Install into the current V3 project root

From the extracted hotfix folder:

```powershell
powershell -ExecutionPolicy Bypass -File .\install_v3_production_hotfix.ps1
```

The installer creates a timestamped backup and does **not** deploy.

After installation, deploy the existing project root with the same Cloud Run
command used for revision `00027-fdc`.
