# V3 Block 6 — Real Business Knowledge + Deterministic Quote Integration

Block 6 connects the V3 brain to two existing production assets:

1. `business_knowledge_service.py`
2. `quote_service.py`

It still does NOT connect to:
- Instagram
- Gmail
- Cloud Run

## New files

- `business_knowledge_adapter_v3.py`
- `quote_adapter_v3.py`
- `business_answer_service_v3.py`
- `business_question_coordinator_v3.py`
- `test_block6_offline_business_v3.py`
- `test_live_business_services_v3.py`

## Architecture

Business question:

```text
ConversationOrchestrator
    ↓
ANSWER_BUSINESS_QUESTION
    ↓
BusinessAnswerServiceV3
    ↓
approved Google Sheets knowledge
    ↓
Gemini phrasing only
    ↓
BUSINESS_QUESTION_RESOLVED
    ↓
resume exact previous state
```

Quote:

```text
FlowState.QUOTE_READY
    ↓
QuoteAdapterV3
    ↓
existing quote_service.calculate_quote()
    ↓
existing Pricing sheet
    ↓
deterministic Python total
```

Gemini never calculates or changes pricing.

## Run offline first

```powershell
python -m py_compile business_knowledge_adapter_v3.py quote_adapter_v3.py business_answer_service_v3.py business_question_coordinator_v3.py test_block6_offline_business_v3.py test_live_business_services_v3.py
python test_block6_offline_business_v3.py
```

Then run the real local integration:

```powershell
python test_live_business_services_v3.py
```

The live script uses:
- your existing project `.env`
- your existing Google service-account credentials
- your live AI Quote Assistant Database
- your current Pricing / Packages / Business_Info / FAQs tabs
- your real Gemini API key

It does NOT send any Instagram message or email.

Do not deploy yet.

The next block, after Block 6 passes, should create the V3 response renderer and
a local end-to-end customer conversation using real business answers and real
quote calculations before touching the webhook.
