# V3 Block 5 — Conversation Orchestrator + Response Plan

Blocks 1–4 established:

1. deterministic state machine;
2. common button/text events;
3. state-specific Gemini semantic boundary;
4. real Gemini semantic behavior.

Block 5 adds the single orchestration entry point that `main.py` will later use.

## Architecture

```text
Customer text / button
        ↓
ConversationOrchestrator
        ↓
Semantic interpreter (text only)
        ↓
EventNormalizer
        ↓
ConversationEvent
        ↓
ConversationStateMachine
        ↓
ResponsePlan
        ↓
future channel renderer
```

## Important new files

- `conversation_orchestrator.py`
- `response_plan.py`
- `turn_logger.py`
- `test_conversation_orchestrator_v3.py`
- `test_full_conversation_v3.py`

## Why ResponsePlan matters

The conversation brain does not send Instagram messages directly.

For example:

```text
ResponseAction.ASK_FIELD
next_field=coverage_type
options=[Photography, Videography, Both]
```

Later the Instagram renderer can turn that into a natural message or buttons.

Likewise a business question becomes:

```text
ResponseAction.ANSWER_BUSINESS_QUESTION
question_type=PACKAGE_PRICING
```

A separate business-answer layer will answer it from approved Sheets knowledge,
then signal `BUSINESS_QUESTION_RESOLVED`.

## Structured diagnostics

Every orchestrated turn records:

- state before
- quote before
- customer message
- semantic interpretation
- normalized event
- state after
- quote after
- response plan
- error, if any

This is the debugging visibility the old architecture lacked.

## Run

```powershell
python -m py_compile conversation_models.py conversation_events.py conversation_state_machine.py semantic_contract.py event_normalizer.py gemini_semantic_adapter.py response_plan.py turn_logger.py conversation_orchestrator.py test_conversation_orchestrator_v3.py test_full_conversation_v3.py
python test_conversation_orchestrator_v3.py
python test_full_conversation_v3.py
```

Do not deploy yet.

The next block should integrate the existing approved business knowledge and
deterministic quote calculation behind adapters, still locally before
Instagram.
