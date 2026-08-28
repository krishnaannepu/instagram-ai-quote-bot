# V3 Block 10 — Speak to Team + Human Handoff + Callback

Block 10 migrates the remaining human-contact flow out of the legacy
`main.py` controller.

## V3 now owns

```text
POST_QUOTE / quote conversation / other supported state
    ↓
Speak to Team
    ↓
HANDOFF_OPTIONS
    ├─ Request Callback
    │      ↓
    │  CALLBACK_PHONE
    │      ↓
    │  CALLBACK_PREFERENCE
    │      ↓
    │  CALLBACK_RECORDED
    │      ↓
    │  Start New Quote / Finish
    │
    ├─ Start New Quote
    └─ Finish
```

It also supports a direct natural-language callback request during an active
quote.

## Preserved behavior

- Human handoff creates/updates a permanent lead.
- First handoff sends one owner notification.
- Repeated handoff does not send duplicate notifications.
- If a final quote and customer email are already known, handoff can still
  deliver the customer quote if it has not already been emailed.
- Callback phone is validated deterministically in Python.
- Callback preference is canonical: ASAP, Morning, Afternoon.
- Callback lead data is updated before/alongside notification.
- Duplicate callback requests are blocked.
- After callback recording only Start New Quote / Finish are shown.
- UK office-open behavior remains 09:00 <= hour < 17:00, matching the current
  application behavior.
- Customer-facing messages do not use the old business name or the prohibited
  customer-facing term.

## Important files added/updated

New:
- `handoff_callback_service_v3.py`
- `test_block10_handoff_semantic_contract_v3.py`
- `test_block10_handoff_callback_v3.py`
- `test_live_handoff_semantics_v3.py`

Updated:
- `conversation_models.py`
- `conversation_events.py`
- `conversation_state_machine.py`
- `semantic_contract.py`
- `gemini_semantic_adapter.py`
- `event_normalizer.py`
- `response_plan.py`
- `conversation_orchestrator.py`
- `customer_response_renderer_v3.py`
- `lead_persistence_adapter_v3.py`
- `email_delivery_adapter_v3.py`
- `local_conversation_runtime_v3.py`
- `v3_runtime_factory.py`
- `test_all_v3_offline.py`

## Run

Compile the Block 10 files:

```powershell
python -m py_compile conversation_models.py conversation_events.py conversation_state_machine.py semantic_contract.py gemini_semantic_adapter.py event_normalizer.py response_plan.py conversation_orchestrator.py customer_response_renderer_v3.py lead_persistence_adapter_v3.py email_delivery_adapter_v3.py handoff_callback_service_v3.py local_conversation_runtime_v3.py v3_runtime_factory.py test_block10_handoff_semantic_contract_v3.py test_block10_handoff_callback_v3.py test_live_handoff_semantics_v3.py
```

Focused offline checks:

```powershell
python test_block10_handoff_semantic_contract_v3.py
python test_block10_handoff_callback_v3.py
```

Full current offline regression:

```powershell
python test_all_v3_offline.py
```

Then the live Gemini-only handoff semantic check:

```powershell
python test_live_handoff_semantics_v3.py
```

The live semantic test does not send Instagram messages or email.

## Do not deploy yet

Block 11 is the final hard cutover:

- replace legacy POST `/instagram/webhook` routing with V3 delegation;
- retain health/privacy/terms/webhook verification endpoints;
- run full webhook integration regression;
- deploy to Cloud Run;
- validate the serving revision and real Instagram conversation.
