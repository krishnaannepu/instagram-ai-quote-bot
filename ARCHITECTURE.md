# Architecture

Every runtime file, what it does, and how it connects. Thirty modules, one
responsibility each. Nothing here is unreachable — if a file is listed, the
running app imports it.

Companion to `README.md`, which covers deploying and debugging.

---

## The one rule

**Gemini understands language. Python decides. Sheets holds the business data.**

Gemini only reports what a message *means* — an action, a field, a value. It
never prices anything, never writes to state, never invents a service or a
package. Python re-checks every interpretation against the approved catalogue
before it can change anything.

Read the layers below as: *meaning comes in from the left, a decision is made in
the middle, words go out to the right.*

---

## Layers at a glance

```
   Instagram
       |
  [1]  main.py ................................ HTTP endpoints
       v3_runtime_factory ...................... builds the object graph once
       |
  [2]  meta_webhook_parser_v3 ................. unpack Meta's payload
       instagram_channel_adapter_v3 ............ per-message loop, logging, safety
       session_repository_v3 ................... whose conversation is this
       |
  [3]  local_conversation_runtime_v3 .......... which service handles this plan
       conversation_orchestrator ............... guard, route, plan     <-- the hub
         gemini_semantic_adapter ....... [5] .... what did they mean?
         event_normalizer .............. [3] .... meaning -> event
         conversation_state_machine .... [3] .... the only thing that changes state
       |
  [6]  customer_response_renderer_v3 .......... decision -> words
       instagram_sender_v3 / instagram_service . send it
       |
       Instagram

  [4]  conversation_models, conversation_events, semantic_contract,
       response_plan ........................... the shared vocabulary
  [7]  business knowledge     [8] pricing      [9] sheets + email
  [10] handoff / callback     [11] turn_logger
```

---

## 1. Entry and wiring

### `main.py`
The FastAPI app and the only file Cloud Run runs directly.

- Endpoints: `GET /` health, `GET|POST /instagram/webhook`, `GET /instagram/callback`, plus the legal pages Meta requires (`/privacy-policy`, `/terms`, `/data-deletion`).
- `get_v3_channel()` builds the app graph **lazily**, on the first webhook, so health and verification endpoints stay up even if Sheets or Gemini is unavailable at boot.
- Deliberately contains **no conversation logic**. It parses nothing and decides nothing — it hands the payload straight to the channel adapter.
- On failure it acknowledges the webhook rather than returning an error, because Meta retries non-2xx and would replay the same broken message.

*Imports:* `v3_runtime_factory` &nbsp;·&nbsp; *Used by:* Cloud Run

### `v3_runtime_factory.py`
Constructs every object once and wires them together.

- One function, `build_instagram_channel_v3()`, that instantiates the adapters, services, orchestrator and renderer and connects them.
- This is the only place dependencies are chosen, which is what makes every other module testable — tests build the same graph with fakes.

*Imports:* 16 modules (everything below) &nbsp;·&nbsp; *Used by:* `main`

---

## 2. Instagram channel

### `meta_webhook_parser_v3.py`
Turns Meta's nested JSON into a flat list of messages.

- Produces `IncomingInstagramMessage` objects: sender, message id, text or button payload, typed by `IncomingMessageType`.
- Filters out echoes and non-message events so nothing downstream has to know Meta's payload shape.

*Imports:* nothing &nbsp;·&nbsp; *Used by:* `instagram_channel_adapter_v3`, `v3_runtime_factory`

### `instagram_channel_adapter_v3.py`
The per-message loop, and the last line of defence.

- For each incoming message: load the session, run the turn, save, send the replies.
- **Idempotency** — skips a message id it has already processed, so a Meta retry cannot duplicate a lead or an email.
- **Error safety** — if a turn raises, it logs the turn record and sends the customer a real message offering Speak to Team. A failed turn must never reach someone as silence.
- Emits one `v3_turn` log line per message. This is the record you read when debugging.

*Imports:* `local_conversation_runtime_v3`, `session_repository_v3`, `meta_webhook_parser_v3`, `instagram_sender_v3`, `customer_response_renderer_v3`, `turn_logger`

### `instagram_sender_v3.py`
The seam between rendered messages and the Instagram API.

- `InstagramSender` is the interface; `ExistingInstagramServiceSenderV3` is the real implementation.
- Exists so tests can record what would have been sent instead of calling Meta.

*Imports:* `instagram_service`, `customer_response_renderer_v3`

### `instagram_service.py`
The raw HTTP call to Meta's Send API.

- `send_instagram_menu()` — posts message text plus quick-reply buttons.
- The only file that talks to `graph.instagram.com`.

*Imports:* `httpx`, `dotenv`

### `session_repository_v3.py`
Where a customer's conversation lives between messages.

- `SessionRepository` is the interface; `InMemorySessionRepositoryV3` is the current implementation.
- **This is the main open risk.** State lives in process memory, so a restart, a new revision, or Cloud Run scaling past one instance drops in-flight conversations. Swapping in a Firestore implementation is a change to this one file.

*Imports:* `conversation_models`

---

## 3. The conversation core

### `local_conversation_runtime_v3.py`
Decides which service fulfils the plan the orchestrator produced.

- Runs the turn, then dispatches on the plan's action: a business question goes to the coordinator, a completed quote to the pricing service, an email to the delivery adapter, a handoff to the handoff service.
- Channel-independent — it knows nothing about Instagram, which is why the same runtime drives the offline tests.

*Imports:* `conversation_orchestrator`, `business_question_coordinator_v3`, `quote_completion_service_v3`, `email_delivery_adapter_v3`, `handoff_callback_service_v3`, `customer_response_renderer_v3`, `response_plan`, `conversation_models`

### `conversation_orchestrator.py`
The hub. Everything a turn needs happens here, in order.

1. **Deterministic short-circuits** — "stop" ends the chat, a phone number at the callback step, an email address at the email step. These run before Gemini so they work even if the model is down.
2. **Interpret** — ask `gemini_semantic_adapter` what the message meant.
3. **Route intent** (`_route_field_intent`) — decide what that meaning means *for this state*. A value at IDLE starts a quote; a value for the field being asked advances the flow; a value for any other field is recorded as a change; a change with no field becomes "what would you like to change?".
4. **Guard** (`_guard_catalogue_value`) — every value is checked against the approved catalogue. An invalid one is rejected with the real options, never stored.
5. **Normalise, transition, plan** — hand off to the normaliser and state machine, then build a `ResponsePlan`.

Also builds the turn log, and wraps failures in `ConversationOrchestratorError` carrying that log.

*Imports:* `conversation_state_machine`, `event_normalizer`, `semantic_contract`, `response_plan`, `conversation_events`, `conversation_models`, `turn_logger`

### `event_normalizer.py`
Translates a Gemini interpretation, or a button press, into one `ConversationEvent`.

- `from_semantic()` for typed messages, `from_button()` for quick replies.
- The state machine only ever sees events, never Gemini output — which is what keeps the model out of the decision.

*Imports:* `semantic_contract`, `conversation_events`, `conversation_models`

### `conversation_state_machine.py`
The only code allowed to change `ConversationContext`.

- One method, `handle(context, event)`, returning a `TransitionResult`.
- Applies quote fields, advances the flow, manages the resume stack for interruptions, invalidates a stale quote when a priced detail changes.
- Every mutation is logged as a `TransitionRecord`, so a conversation's history is inspectable.

*Imports:* `conversation_events`, `conversation_models`

---

## 4. The shared vocabulary

These four define the words the rest of the system speaks. They import almost
nothing, and almost everything imports them.

### `conversation_models.py`
The data every other module agrees on. Imported by **16** files.

- `FlowState` — the 20 conversation states.
- `QuoteData` — the seven quote fields, with `get`/`set`/`as_dict`.
- `ConversationContext` — state, quote, customer, lifecycle, resume stack, deferred fields, transition log.
- `expected_field()` — which field the current state is asking for. Derived from state, which is why clearing a field is never enough on its own; the flow has to be rewound too.

### `conversation_events.py`
`EventType` and `ConversationEvent` — the vocabulary of things that can happen. Small and stable by design.

### `semantic_contract.py`
**The real conversation design lives here.**

- `SemanticAction` — everything Gemini may return.
- `SemanticInterpretation` — the shape it returns it in, including `changes` for messages carrying several details.
- `STATE_ALLOWED_ACTIONS` — which actions are legal in which state, built from `ALWAYS_ALLOWED` (greet, ask, check status, reach a human, finish) plus `QUOTE_EDITABLE_STATES`.

Most bugs in this project have been this table being narrower than how customers actually talk. Widen it here first.

### `response_plan.py`
`ResponseAction` and `ResponsePlan` — what to say, decided but not yet worded. Keeps the decision separate from the phrasing, so wording changes cannot break logic.

---

## 5. Understanding

### `gemini_semantic_adapter.py`
The only file that talks to Gemini.

- `build_prompt()` — assembles state, expected field, allowed values, catalogue and rules. It is an f-string, so any literal brace in an example must be doubled.
- `parse_response()` — **never raises.** Anything unusable is logged as `v3_contract_gap` and degraded to `UNCLEAR`, because an interpretation failure must not reach the customer as an error.
- Validates only what makes a response uninterpretable. Whether a value arrived in the right order is Python's decision, made in the orchestrator.

*Imports:* `semantic_contract`, `conversation_models`, `google.genai`

---

## 6. Speaking

### `customer_response_renderer_v3.py`
Turns a `ResponsePlan` into the words a customer reads.

- `render_plan()` for ordinary turns, `render_business_answer()` for grounded answers, `render_quote()` for the priced quote.
- Every message passes through one wrapper that prepends a confirmation when the customer asked for a change — so a change is never applied silently.
- Rejections name what was rejected and list the real options.
- Buttons come from `ButtonSpec`; the result is a `RenderedMessage`.

*Imports:* `response_plan`, `business_answer_service_v3`

---

## 7. Business knowledge

### `business_knowledge_service.py`
Reads the approved tabs from Sheets, with a 300-second cache.

- `get_pricing_knowledge()`, `get_package_knowledge()`, `get_business_info()`, `get_faq_knowledge()`.
- Double-checked locking, and it serves the stale cache if a refresh fails rather than taking the bot down.

*Imports:* `sheets_service`

### `business_knowledge_adapter_v3.py`
The V3 view of that cache.

- `get_catalogue()` — the supported services and packages-by-service that every validation checks against.
- `get_pricing(service, package)`, `get_package(...)` — exact row lookups.
- Takes its data source by injection, which is how tests run with fake knowledge and no network.

### `business_answer_service_v3.py`
Answers a business question **only** from approved knowledge.

- `answer()` returns a `BusinessAnswer` with `answer_found` and `should_offer_human`, so an unknown answer becomes an offer of a human rather than an invention.

### `business_question_coordinator_v3.py`
Handles a question without losing the customer's place.

- Builds package comparisons **deterministically from Sheets** when the service is known, so Gemini never generates prices.
- Returns both the answer and a resume plan — the question is answered, then the conversation picks up where it was.

---

## 8. Pricing

### `quote_service.py`
The pricing maths. No LLM, no state, no side effects.

- `calculate_quote()` — base price by coverage, extra hours beyond the included allowance, travel fee.
- Raises if no active pricing rule matches, rather than guessing.

*Imports:* `sheets_service`

### `quote_adapter_v3.py`
Bridges the V3 context to that function.

- `calculate()` for the live quote, `calculate_for_package()` for hypothetical comparisons that must not touch the customer's real selection.

### `quote_completion_service_v3.py`
Everything that happens when a quote is finished: calculate, persist the lead, notify the owner, move to the email step.

---

## 9. Persistence and delivery

### `sheets_service.py`
All Google Sheets access.

- Lazy connection (`_LazySpreadsheet`) so import never blocks on the network.
- Leads and conversation rows; header-driven writes, so reordering columns in the sheet cannot corrupt data.

### `lead_persistence_adapter_v3.py`
The V3 view of lead storage — create on quote completion, create on handoff, update status.

### `email_service.py`
Gmail API access. Supports a local token file and a Secret Manager value, and refuses interactive OAuth in Cloud Run with an actionable message.

### `email_delivery_adapter_v3.py`
Decides *when* to email: the customer's quote, the owner's new-lead notification, handoff and callback alerts. Failures are caught so email trouble never breaks a conversation.

---

## 10. Human handoff

### `handoff_callback_service_v3.py`
Everything about reaching a person.

- `is_office_open()` — UK hours, which changes the wording the customer gets.
- `process_handoff()`, `start_callback()`, `complete_callback()`.
- Guards against duplicates, so asking twice does not send two alerts.

---

## 11. Observability

### `turn_logger.py`
One structured record per customer turn.

- `build_turn_log()` captures state before and after, Gemini's interpretation, the Python event, and the response plan.
- `emit_turn_log()` writes it as single-line JSON, which Cloud Run parses into a queryable entry.

**This is the file that makes the system debuggable.** `interpretation` is what Gemini decided; `event` is what Python decided. If they disagree with what the customer saw, you know which side to fix.

---

## Test kit

Not shipped — excluded by `.gcloudignore`, run by `python run_regressions.py`.

| File | Covers |
|---|---|
| `v3_test_harness.py` | Runs canned Gemini JSON through the **real** adapter, prompt construction included. Never write a double that skips a production step |
| `test_full_turn_matrix_v3.py` | Every state x every action, end to end. **The one to trust** |
| `test_contract_coverage_v3.py` | The adapter never raises; the prompt builds; the prompt asks for every key the parser reads |
| `test_finish_anywhere_v3.py` | "stop" ends the chat from anywhere, without Gemini |
| `test_change_request_v3.py` | Changing one or many details after a quote |
| `test_idle_entry_v3.py` | Typing instead of tapping |
| `test_service_correction_v3.py` | Corrections mid-quote; a failing turn still answers |
| `test_change_and_status_v3.py` | Status questions; invalid values |
| `test_production_screenshot_regression_v3.py` | The original production transcript |
| `test_production_defect_hotfix_v3.py` | Catalogue validation |

---

## Where to change things

| To change | Edit |
|---|---|
| Prices, packages, services | **The Google Sheet.** No deploy needed |
| FAQ answers, business info | **The Google Sheet** |
| What Gemini is allowed to return in a state | `semantic_contract.py` |
| How a message is understood | the prompt in `gemini_semantic_adapter.py` |
| What the bot says | `customer_response_renderer_v3.py` |
| The order fields are asked in | `conversation_models.py` (`QUOTE_FIELD_ORDER`) |
| How a price is worked out | `quote_service.py` |
| When an email is sent | `email_delivery_adapter_v3.py` |
| Office hours | `handoff_callback_service_v3.py` |
| Where sessions are stored | `session_repository_v3.py` |
