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
    SemanticRequest,
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


# The prompt itself must build. It is an f-string, so a literal brace in an
# example - a JSON snippet, say - turns into a format expression and every
# text message fails at construction while buttons keep working.
prompt_failures = []

for state in FlowState:
    context = ConversationContext()
    context.state = state
    context.quote.service = "Wedding"
    context.quote.package = "Basic"

    request = SemanticRequest(
        state=state,
        expected_field=context.expected_field(),
        message_text="duration is 4 hrs coverage is photography",
        allowed_values=["Basic", "Premium"],
        supported_services=["Wedding", "Birthday"],
        packages_for_service=["Basic", "Premium"],
        current_quote=context.quote.as_dict(),
        current_package="Basic",
        deferred_fields=[],
    )

    try:
        prompt = adapter.build_prompt(request)
    except Exception as error:
        prompt_failures.append(
            (state.value, f"{type(error).__name__}: {error}")
        )
        continue

    if '{"field_name": "duration_hours", "value": 4}' not in prompt:
        prompt_failures.append(
            (state.value, "the multi-field JSON example did not survive")
        )

if prompt_failures:
    print(f"{len(prompt_failures)} states could not build a prompt:")
    for state, message in prompt_failures:
        print(f"  {state:24} {message}")

assert not prompt_failures, (
    "the prompt must build in every state with its examples intact"
)

print(f"PASS - the prompt builds in all {len(list(FlowState))} states")


# Every key the parser reads must appear in the response template the prompt
# shows Gemini. That template says "exactly these keys", so a key described in
# prose but missing from the template is a key Gemini will never send - which
# is how "changes" was documented, parsed, tested, and still never arrived.
import inspect
import re

parser_source = "".join(
    inspect.getsource(getattr(GeminiSemanticAdapter, name))
    for name in ("_parse_response_strict", "_parse_changes")
)

parsed_keys = set(
    re.findall(
        r'raw\.get\(\s*["\'](\w+)["\']',
        parser_source,
    )
)

reference_prompt = adapter.build_prompt(
    SemanticRequest(
        state=FlowState.POST_QUOTE,
        expected_field=None,
        message_text="package basic duration 6 hours",
        allowed_values=[],
        supported_services=["Wedding"],
        packages_for_service=["Basic", "Premium"],
        current_quote={"service": "Wedding"},
        current_package="Basic",
        deferred_fields=[],
    )
)

# Only the JSON object itself counts. Prose below it describing a key is
# exactly the mistake being guarded against: the template says "exactly these
# keys", so a key that lives only in prose is a key Gemini will never send.
template_start = reference_prompt.index("Return one JSON object")
object_start = reference_prompt.index("{", template_start)
object_end = reference_prompt.index("\n}", object_start)
response_template = reference_prompt[object_start:object_end]

undocumented = sorted(
    key
    for key in parsed_keys
    if f'"{key}"' not in response_template
)

if undocumented:
    print("keys the parser reads but the prompt never asks for:")
    for key in undocumented:
        print(f"  {key}")

assert not undocumented, (
    "every key the parser reads must be in the response template, "
    "or Gemini will never send it"
)

print(
    f"PASS - all {len(parsed_keys)} parsed keys appear in the response "
    f"template Gemini is given"
)


print()
print("=" * 72)
print("V3 CONTRACT COVERAGE SWEEP PASSED")
print("=" * 72)
