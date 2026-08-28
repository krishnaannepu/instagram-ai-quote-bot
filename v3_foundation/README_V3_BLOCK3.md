# V3 Block 3 — State-Specific Gemini Semantic Adapter

Block 3 connects the AI contract without giving Gemini control over state.

## Architecture now

Customer text
→ `GeminiSemanticAdapter`
→ `SemanticInterpretation`
→ `EventNormalizer`
→ `ConversationEvent`
→ `ConversationStateMachine`
→ deterministic Python transition

Gemini never receives a session object that it can mutate.

## New file

`gemini_semantic_adapter.py`

It:
- builds a prompt from the authoritative `FlowState`;
- limits Gemini to actions allowed in that state;
- validates Gemini JSON again in Python;
- rejects wrong-field answers;
- rejects impossible state/action combinations;
- explicitly protects travel and coverage semantics;
- explicitly separates package questions before selection from package
  reconsideration after selection.

## Offline tests

These tests DO NOT call the Gemini API:

```powershell
python test_gemini_semantic_adapter_v3.py
python test_semantic_pipeline_v3.py
```

They validate the adapter boundary and the complete:

semantic output
→ normalizer
→ state machine

pipeline.

## Optional live Gemini smoke test

Do not run a live Gemini test yet. The next block will add a controlled live
smoke-test script that uses your `.env` and compares actual Gemini output
against the state contract.

This keeps API variability separate from the deterministic architecture.
