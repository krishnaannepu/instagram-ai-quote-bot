"""
Contract coverage sweep.

Every conversation state crossed with every semantic action Gemini can return.
No combination may reach the customer as a failure.

This exists because three separate production incidents had the same shape: a
state/action pair the contract refused, surfacing as silence or an apology.
Individual transcripts kept finding them one at a time. This finds them all.

Two guarantees:
  HARD  - parse_response must never raise for a well-formed Gemini response
  SOFT  - actions a customer can reasonably use at any point must be accepted,
          not merely degraded

Offline: no Gemini, no Sheets, no network.
"""

from conversation_models import ConversationContext, FlowState
from gemini_semantic_adapter import (
    GeminiSemanticAdapter,
    GeminiSemanticAdapterError,
)
from semantic_contract import SemanticAction

adapter = GeminiSemanticAdapter(client=None)

RESPONSES = {
    "FIELD_VALUE service": {
        "action": "FIELD_VALUE", "field_name": "service", "value": "Wedding"},
    "FIELD_VALUE package": {
        "action": "FIELD_VALUE", "field_name": "package", "value": "Basic"},
    "FIELD_VALUE duration": {
        "action": "FIELD_VALUE", "field_name": "duration_hours", "value": 8},
    "CHANGE_FIELD service": {
        "action": "CHANGE_FIELD", "field_name": "service", "value": "Wedding"},
    "CHANGE_FIELD package": {
        "action": "CHANGE_FIELD", "field_name": "package", "value": "Premium"},
    "BUSINESS_QUESTION": {
        "action": "BUSINESS_QUESTION", "question_text": "do you do drone?"},
    "STATUS_QUESTION": {
        "action": "STATUS_QUESTION", "question_text": "what have I picked"},
    "SPEAK_TO_TEAM": {"action": "SPEAK_TO_TEAM"},
    "REQUEST_CALLBACK": {"action": "REQUEST_CALLBACK"},
    "GREETING": {"action": "GREETING"},
}

# Incomplete and malformed responses. Gemini does not always fill every field,
# and "can I change something?" genuinely has no field or value to report.
# None of these may fail a turn. This set exists because the first version of
# this sweep only tested complete payloads, and five incomplete shapes reached
# production still raising.
PARTIAL = {
    "CHANGE_FIELD bare": {"action": "CHANGE_FIELD"},
    "CHANGE_FIELD no value": {"action": "CHANGE_FIELD", "field_name": "package"},
    "CHANGE_FIELD no field": {"action": "CHANGE_FIELD", "value": "Premium"},
    "FIELD_VALUE bare": {"action": "FIELD_VALUE"},
    "FIELD_VALUE no value": {"action": "FIELD_VALUE", "field_name": "service"},
    "BUSINESS_QUESTION no text": {"action": "BUSINESS_QUESTION"},
    "STATUS_QUESTION no text": {"action": "STATUS_QUESTION"},
    "unknown action": {"action": "TOTALLY_MADE_UP"},
    "empty object": {},
    "not json": "<<< not json at all >>>",
    "changes empty": {"action": "CHANGE_FIELD", "changes": []},
    "changes not a list": {"action": "CHANGE_FIELD", "changes": "package"},
    "changes junk entries": {
        "action": "CHANGE_FIELD",
        "changes": ["package", {"field_name": "nope"}, {"value": 3}],
    },
    "changes two fields": {
        "action": "CHANGE_FIELD",
        "changes": [
            {"field_name": "duration_hours", "value": 4},
            {"field_name": "coverage_type", "value": "Photography"},
        ],
    },
}


# A customer can do these at any point in any conversation.
UNIVERSAL = [
    "GREETING",
    "BUSINESS_QUESTION",
    "STATUS_QUESTION",
    "SPEAK_TO_TEAM",
    "REQUEST_CALLBACK",
]

# BUSINESS_INTERRUPT is transient - the coordinator owns it, never Gemini.
STATES = [state for state in FlowState if state != FlowState.BUSINESS_INTERRUPT]


def interpret(state, payload):
    context = ConversationContext()
    context.state = state
    context.quote.service = "Wedding"
    context.quote.package = "Basic"

    return adapter.parse_response(context, dict(payload))


hard_failures = []
soft_failures = []

for state in STATES:
    for label, payload in RESPONSES.items():
        try:
            result = interpret(state, payload)
        except GeminiSemanticAdapterError as error:
            hard_failures.append((state.value, label, str(error)))
            continue
        except Exception as error:
            hard_failures.append(
                (state.value, label, f"{type(error).__name__}: {error}")
            )
            continue

        degraded = result.metadata.get("contract_gap") is True

        if degraded and label in UNIVERSAL:
            soft_failures.append((state.value, label))

if hard_failures:
    print(f"{len(hard_failures)} HARD failures - these reach the customer:")
    for state, label, message in hard_failures:
        print(f"  {state:24} {label:22} {message}")

if soft_failures:
    print(f"{len(soft_failures)} universal actions refused:")
    for state, label in soft_failures:
        print(f"  {state:24} {label}")

assert not hard_failures, "a well-formed Gemini response must never raise"
assert not soft_failures, (
    "greetings, questions, status checks and reaching a human "
    "must work in every state"
)

checked = len(STATES) * len(RESPONSES)
print(
    f"PASS - {checked} state/action combinations "
    f"({len(STATES)} states x {len(RESPONSES)} actions), no failures"
)


# UNCLEAR must survive everywhere, because it is what a degrade becomes.
for state in STATES:
    context = ConversationContext()
    context.state = state
    result = adapter.parse_response(context, {"action": "UNCLEAR"})
    assert result.action == SemanticAction.UNCLEAR

print(f"PASS - UNCLEAR is accepted in all {len(STATES)} states")


# Incomplete responses must never fail a turn.
partial_failures = []

for state in STATES:
    for label, payload in PARTIAL.items():
        context = ConversationContext()
        context.state = state
        context.quote.service = "Wedding"
        context.quote.package = "Basic"

        body = payload if isinstance(payload, str) else dict(payload)

        try:
            adapter.parse_response(context, body)
        except Exception as error:
            partial_failures.append(
                (state.value, label, f"{type(error).__name__}: {error}")
            )

if partial_failures:
    print(f"{len(partial_failures)} incomplete responses failed:")
    for state, label, message in partial_failures:
        print(f"  {state:24} {label:26} {message}")

assert not partial_failures, (
    "an incomplete Gemini response must degrade, never fail the turn"
)

print(
    f"PASS - {len(STATES) * len(PARTIAL)} incomplete/malformed responses "
    f"all handled without failing a turn"
)


print()
print("=" * 72)
print("V3 CONTRACT COVERAGE SWEEP PASSED")
print("=" * 72)
