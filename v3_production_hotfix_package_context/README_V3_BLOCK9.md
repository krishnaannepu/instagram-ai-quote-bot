# V3 Block 9 — Quote Persistence + Email + Post-Quote

Block 9 migrates the next part of the legacy controller before the hard
`main.py` cutover.

## What is now inside V3

```text
QUOTE_READY
    ↓
deterministic quote_service
    ↓
Leads persistence
    ↓
EMAIL_CONFIRMATION
    ├─ Yes → EMAIL_ADDRESS → customer quote email
    └─ No  → POST_QUOTE
```

At `POST_QUOTE`, the customer sees:

- Speak to Team
- Start New Quote
- Finish

`Speak to Team` is rendered now but is intentionally implemented in Block 10
with callback/handoff behavior. Do not deploy before Block 10.

## Important customer-email change

V3 does NOT call the old `send_customer_quote_email()` because its
customer-facing subject/body contain the old business name.

V3 uses the existing generic Gmail `send_email()` transport and generates a
new customer-safe email body.

## New files

- `lead_persistence_adapter_v3.py`
- `email_delivery_adapter_v3.py`
- `quote_completion_service_v3.py`
- `test_block9_postquote_email_v3.py`
- `test_instagram_sender_compat_v3.py`

## Updated files

- `conversation_models.py`
- `conversation_events.py`
- `conversation_state_machine.py`
- `semantic_contract.py`
- `gemini_semantic_adapter.py`
- `event_normalizer.py`
- `response_plan.py`
- `conversation_orchestrator.py`
- `customer_response_renderer_v3.py`
- `local_conversation_runtime_v3.py`
- `instagram_sender_v3.py`
- `instagram_channel_adapter_v3.py`
- `v3_runtime_factory.py`

## Run

```powershell
python -m py_compile conversation_models.py conversation_events.py conversation_state_machine.py semantic_contract.py gemini_semantic_adapter.py event_normalizer.py response_plan.py conversation_orchestrator.py customer_response_renderer_v3.py lead_persistence_adapter_v3.py email_delivery_adapter_v3.py quote_completion_service_v3.py local_conversation_runtime_v3.py instagram_sender_v3.py instagram_channel_adapter_v3.py v3_runtime_factory.py test_block9_postquote_email_v3.py test_instagram_sender_compat_v3.py

python test_block9_postquote_email_v3.py
python test_instagram_sender_compat_v3.py
```

Do not deploy yet.

Block 10 migrates:
- Speak to Team
- human handoff notification
- Request Callback
- callback phone
- callback preference
- post-callback options

Only after Block 10 passes should the legacy `main.py` webhook be replaced.


## Recommended regression command

After the two focused Block 9 checks pass, you can run the current supported
offline suite in one command:

```powershell
python test_all_v3_offline.py
```

Older block-specific runtime scripts may represent earlier runtime constructor
shapes; use the current Block 9 tests and `test_all_v3_offline.py` as the
authoritative regression set from this point forward.
