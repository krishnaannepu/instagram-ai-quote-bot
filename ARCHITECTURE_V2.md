# Instagram Quote Assistant — Conversation Engine V2

## Why this refactor exists

The previous application had several independent pieces of conversation state
(`current_stage`, `expected_quote_field`, deferred flags, package-reconfirmation
flags, prior business-question context, etc.) that could all influence routing.
That made individual fixes work in isolation while a different conversation
path could still fail.

V2 gives the AI quote conversation one authoritative state machine.

## New architecture

Incoming Instagram message
→ main.py channel/UI routing
→ conversation_engine.py
→ current FlowState gets first interpretation priority
→ Gemini performs constrained semantic interpretation
→ Python validates values and decides the transition
→ business questions act as temporary interrupts
→ resume the authoritative state
→ deterministic quote_service.py calculates prices

### Authoritative quote states

- IDLE
- QUOTE_SERVICE
- QUOTE_PACKAGE
- QUOTE_COVERAGE
- QUOTE_TRAVEL
- QUOTE_DURATION
- QUOTE_DATE
- QUOTE_LOCATION
- DEFERRED_REVIEW_READY
- PACKAGE_RECONFIRMATION
- QUOTE_READY
- FINISHED

`current_stage` is still retained in `main.py` for outer UI/channel operations
such as email collection, callback collection, human handoff and post-quote
menus. `flow_state` owns the natural-language quote conversation.

## New files

### conversation_state.py
Owns FlowState, field/state mapping, transition logging and the resume stack.

### conversation_engine.py
The central orchestrator. This replaces the old large collection of overlapping
routing rules in ai_conversation_service.py.

### ai_conversation_service.py
Now a small compatibility facade. Existing imports from main.py continue to
work while the implementation lives in conversation_engine.py.

## Modified files

### main.py
- Uses Conversation Engine V2.
- Keeps email, callback, handoff and post-quote UI stages.
- Uses generic `resume_prompt` handling after side questions.
- Fixed the fallback package-reconfirmation code path.
- Keeps explicit post-quote actions:
  Speak to Team / Start New Quote / Finish.
- Keeps post-callback actions:
  Start New Quote / Finish.

### gemini_service.py
- Retains multilingual structured interpretation.
- Receives authoritative flow-state/resume context.
- Gemini interprets meaning; Python decides state transitions.
- Existing grounding and business-knowledge restrictions remain.

### sheets_service.py
- Google Sheets connection is lazy rather than opening the workbook during
  module import.
- A temporary Sheets 503 therefore does not prevent FastAPI from importing.
- Connection attempts use a small retry window.
- The duplicate `get_pricing_rule()` definition was removed.

### quote_service.py
Pricing architecture is unchanged. Python remains deterministic and authoritative.

### business_knowledge_service.py
Retained. Google Sheets remains the business-editable source of truth.

### instagram_service.py
Retained.

## Behavioral contracts covered by regression tests

1. Package comparison is an interrupt, not a package selection.
2. If a package was already selected, a comparison can lead to a keep/switch
   decision without losing the interrupted quote field.
3. A side question such as `Prices??` does not make a pending package decision
   disappear.
4. `Hmm` / bare acknowledgements cannot accidentally leave that decision.
5. `both` while coverage is expected means Photography + Videography, not
   "both packages".
6. Uncertain fields are deferred instead of repeatedly asked.
7. Before final quote generation, unresolved deferred fields are reviewed.
8. Natural action phrases such as `okay kardo` can mean proceed/Yes in the
   appropriate binary state.
9. Only fields explicitly supplied in the newest message may update quote
   state (`fields_to_update` is authoritative).
10. A request for differences + prices returns both kinds of information.
11. Post-quote package changes invalidate a stale quote and permit deterministic
    recalculation.

## Files to KEEP from your existing project

The uploaded set did not include these, and `main.py` still intentionally uses
them:

- `email_service.py`
- `button_flow_service.py`
- `.env`
- `credentials/`
- your Dockerfile / Procfile / requirements files if currently used
- existing Gmail OAuth / Secret Manager deployment configuration

Do not delete them.

## Installation

Back up the current project.

Replace these project-root files with the V2 versions:

- main.py
- ai_conversation_service.py
- gemini_service.py
- sheets_service.py
- business_knowledge_service.py
- instagram_service.py
- quote_service.py

Add:

- conversation_state.py
- conversation_engine.py
- test_architecture_contract_v2.py
- test_conversation_engine_v2.py

## Local validation

Run:

```powershell
python -m py_compile main.py conversation_state.py conversation_engine.py ai_conversation_service.py gemini_service.py business_knowledge_service.py instagram_service.py quote_service.py sheets_service.py
python test_architecture_contract_v2.py
python test_conversation_engine_v2.py
```

Do not deploy unless all commands pass.

## Suggested Instagram regression conversation

Use a fresh conversation/session:

1. Start a Wedding quote.
2. Select Basic.
3. While coverage is being asked: `wait what's the difference between Basic and Premium?`
4. Ask: `Prices??`
5. Say: `Hmm`
6. Say: `Premium kardo`
7. Say: `Both`
8. For travel say: `maybe`
9. Give duration, date and location.
10. At the unresolved-field checkpoint say: `okay kardo`
11. Confirm travel naturally.
12. Generate the quote.
13. Ask a business side question at the email-confirmation step.
14. Confirm the email choice.
15. Verify post-quote buttons.
16. Verify callback flow and the reduced post-callback menu.

The system should always return to the state that was pending before a side
question.

## Deployment

After local validation:

```powershell
gcloud run deploy instagram-ai-quote-bot `
  --source . `
  --region=europe-west2 `
  --allow-unauthenticated
```

Then verify the ready revision and inspect logs before starting the Instagram
conversation.

## Production-hardening note

V2 fixes the orchestration architecture, but active sessions are still stored
in process memory by `main.py`. For the current MVP/single-instance validation
that is acceptable, but a Cloud Run restart or multi-instance scaling can
still lose an active conversation.

The next production-hardening step should be a persistent conversation
repository (Firestore is a good fit on Cloud Run) storing at minimum:

- sender_id
- flow_state
- quote fields
- resume_stack
- deferred fields
- current UI stage
- last message ID
- updated_at

That persistence migration should be done after V2 conversation behavior is
stable rather than mixing another infrastructure change into this refactor.
