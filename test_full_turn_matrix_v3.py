"""
Full-turn matrix: every state crossed with every action, end to end.

test_contract_coverage_v3 checks interpretation. That is only half a turn, and
the halves can disagree: the adapter accepted GREETING everywhere while the
state machine accepted it only at IDLE, so "Hi" after finishing a quote failed
in production while that sweep stayed green. Seventy-two of these 285 turns
were crashing at that point.

This runs the real orchestrator - guard, routing, normaliser, state machine,
response plan - for every combination. No turn may raise, because a raised
turn reaches the customer as an apology.

Offline: fake Sheets knowledge, canned Gemini JSON through the real adapter.
"""

from conversation_models import ConversationContext, FlowState
from customer_response_renderer_v3 import CustomerResponseRendererV3
from response_plan import ResponseAction
from v3_test_harness import build_orchestrator

RESPONSES = {
    "FIELD_VALUE service": {
        "action": "FIELD_VALUE", "field_name": "service", "value": "Wedding"},
    "FIELD_VALUE package": {
        "action": "FIELD_VALUE", "field_name": "package", "value": "Basic"},
    "FIELD_VALUE duration": {
        "action": "FIELD_VALUE", "field_name": "duration_hours", "value": 8},
    "CHANGE_FIELD service": {
        "action": "CHANGE_FIELD", "field_name": "service", "value": "Birthday"},
    "CHANGE_FIELD bare": {"action": "CHANGE_FIELD"},
    "CHANGE_FIELD multi": {
        "action": "CHANGE_FIELD",
        "changes": [
            {"field_name": "duration_hours", "value": 4},
            {"field_name": "coverage_type", "value": "Photography"},
        ],
    },
    "BUSINESS_QUESTION": {
        "action": "BUSINESS_QUESTION", "question_text": "do you do drone?"},
    "STATUS_QUESTION": {
        "action": "STATUS_QUESTION", "question_text": "what have I picked"},
    "PACKAGE_RECONSIDERATION": {
        "action": "PACKAGE_RECONSIDERATION", "question_text": "basic vs premium"},
    "SPEAK_TO_TEAM": {"action": "SPEAK_TO_TEAM"},
    "REQUEST_CALLBACK": {"action": "REQUEST_CALLBACK"},
    "GREETING": {"action": "GREETING"},
    "UNCLEAR": {"action": "UNCLEAR"},
    "FINISH": {"action": "FINISH"},
    "START_NEW_QUOTE": {"action": "START_NEW_QUOTE"},
}

# BUSINESS_INTERRUPT is transient - the coordinator owns it, never Gemini.
STATES = [state for state in FlowState if state != FlowState.BUSINESS_INTERRUPT]

# These plans are completed by the runtime, not rendered directly.
RUNTIME_OWNED = {
    ResponseAction.QUOTE_READY,
    ResponseAction.ANSWER_BUSINESS_QUESTION,
    ResponseAction.ANSWER_PACKAGE_RECONSIDERATION,
    ResponseAction.SEND_QUOTE_EMAIL,
    ResponseAction.PROCESS_HANDOFF_REQUEST,
    ResponseAction.START_CALLBACK_REQUEST,
    ResponseAction.PROCESS_CALLBACK_REQUEST,
}


def context_for(state):
    context = ConversationContext()
    context.state = state
    context.quote.service = "Wedding"
    context.quote.package = "Basic"
    return context


renderer = CustomerResponseRendererV3()

turn_failures = []
render_failures = []

for state in STATES:
    for label, payload in RESPONSES.items():
        context = context_for(state)
        orchestrator = build_orchestrator([dict(payload)])

        try:
            turn = orchestrator.handle_text(
                context=context,
                message_text="a customer message",
            )
        except Exception as error:
            turn_failures.append(
                (state.value, label, f"{type(error).__name__}: {error}")
            )
            continue

        if turn.response_plan.action in RUNTIME_OWNED:
            continue

        try:
            message = renderer.render_plan(turn.response_plan)
        except Exception as error:
            render_failures.append(
                (state.value, label, f"{type(error).__name__}: {error}")
            )
            continue

        if not (message.text or "").strip():
            render_failures.append(
                (state.value, label, "rendered an empty message")
            )

if turn_failures:
    print(f"{len(turn_failures)} turns raised:")
    for state, label, message in turn_failures[:20]:
        print(f"  {state:24} {label:26} {message}")

if render_failures:
    print(f"{len(render_failures)} plans could not be rendered:")
    for state, label, message in render_failures[:20]:
        print(f"  {state:24} {label:26} {message}")

assert not turn_failures, (
    "a raised turn reaches the customer as an apology - no combination may raise"
)
assert not render_failures, (
    "every plan the runtime hands to the renderer must produce a message"
)

total = len(STATES) * len(RESPONSES)
print(
    f"PASS - {total} full turns ({len(STATES)} states x {len(RESPONSES)} "
    f"actions), none raised, all rendered"
)


# The reported failure, kept explicit so it cannot regress quietly.
context = context_for(FlowState.FINISHED)
orchestrator = build_orchestrator([{"action": "GREETING"}])
turn = orchestrator.handle_text(context=context, message_text="Hi")

assert context.state == FlowState.IDLE, (
    "a greeting after finishing must start a fresh conversation"
)
assert context.quote.service is None, "the finished quote must be cleared"
assert turn.response_plan.action == ResponseAction.WELCOME
print("PASS - 'Hi' after finishing starts a new conversation")


# Mid-quote a greeting must not look like a restart.
context = context_for(FlowState.QUOTE_TRAVEL)
orchestrator = build_orchestrator([{"action": "GREETING"}])
turn = orchestrator.handle_text(context=context, message_text="hi are you there")
text = renderer.render_plan(turn.response_plan).text

assert context.state == FlowState.QUOTE_TRAVEL, "a greeting must not reset a quote"
assert context.quote.service == "Wedding"
assert "travel" in text.lower(), "it must pick the quote back up"
print("PASS - a greeting mid-quote resumes instead of restarting")


print()
print("=" * 72)
print("V3 FULL TURN MATRIX PASSED")
print("=" * 72)
