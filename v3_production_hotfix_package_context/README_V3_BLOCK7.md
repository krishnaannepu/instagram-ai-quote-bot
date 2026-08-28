# V3 Block 7 — Local End-to-End Runtime

Block 7 is the first complete customer-conversation runtime, but it is still
local only.

It connects:

```text
real Gemini semantic interpretation
→ one orchestrator
→ one state machine
→ approved Google Sheets business knowledge
→ grounded business answer
→ deterministic quote_service
→ customer-facing response renderer
```

It still does NOT connect to:
- Instagram
- Gmail
- Cloud Run

## Important correction in Block 7

When a package is already selected:

```text
Basic selected
→ customer asks price/package difference
```

the system now does:

```text
answer package comparison/prices
→ tell customer Basic is currently selected
→ ask keep Basic or switch
```

It does not skip the answer.

## New files

- `customer_response_renderer_v3.py`
- `local_conversation_runtime_v3.py`
- `test_block7_local_runtime_v3.py`
- `test_live_local_conversation_v3.py`

Block 7 also modifies:
- `response_plan.py`
- `conversation_orchestrator.py`
- `business_question_coordinator_v3.py`

## Run offline

```powershell
python -m py_compile response_plan.py conversation_orchestrator.py business_question_coordinator_v3.py customer_response_renderer_v3.py local_conversation_runtime_v3.py test_block7_local_runtime_v3.py test_live_local_conversation_v3.py
python test_block7_local_runtime_v3.py
```

Then run the real local conversation:

```powershell
python test_live_local_conversation_v3.py
```

Expected final result:

```text
V3 BLOCK 7 LIVE LOCAL END-TO-END CONVERSATION PASSED
```

Do not deploy yet.

If Block 7 passes locally, the next step is a webhook/channel adapter that lets
the existing Instagram webhook call this runtime without containing quote
routing logic.
