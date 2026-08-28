from conversation_models import ConversationContext, FlowState
from conversation_state_machine import ConversationStateMachine
from event_normalizer import EventNormalizer
from gemini_semantic_adapter import GeminiSemanticAdapter


adapter = GeminiSemanticAdapter(
    client=object()
)

normalizer = EventNormalizer()
machine = ConversationStateMachine()


def semantic_from_raw(
    context,
    raw,
):
    interpretation = adapter.parse_response(
        context=context,
        raw=raw,
    )

    return normalizer.from_semantic(
        context=context,
        interpretation=interpretation,
    )


# ------------------------------------------------------------------
# Conversation path:
# Basic selected -> coverage expected -> package comparison ->
# switch Premium -> resume coverage -> Both.
# ------------------------------------------------------------------

context = ConversationContext(
    state=FlowState.QUOTE_COVERAGE
)

context.quote.service = "Wedding"
context.quote.package = "Basic"

comparison_event = semantic_from_raw(
    context,
    {
        "action":
            "PACKAGE_RECONSIDERATION",
        "question_type":
            "PACKAGE_COMPARISON",
        "question_text":
            "What's the difference between Basic and Premium?",
        "confidence":
            0.99,
        "language":
            "English",
        "metadata":
            {},
    },
)

machine.handle(
    context,
    comparison_event,
)

assert (
    context.state
    == FlowState.PACKAGE_RECONFIRMATION
)

switch_event = semantic_from_raw(
    context,
    {
        "action":
            "SWITCH_PACKAGE",
        "field_name":
            None,
        "value":
            "Premium",
        "question_type":
            None,
        "question_text":
            None,
        "confidence":
            0.99,
        "language":
            "Hinglish",
        "metadata":
            {},
    },
)

result = machine.handle(
    context,
    switch_event,
)

assert context.quote.package == "Premium"
assert result.state == FlowState.QUOTE_COVERAGE

coverage_event = semantic_from_raw(
    context,
    {
        "action":
            "FIELD_VALUE",
        "field_name":
            "coverage_type",
        "value":
            "Both",
        "question_type":
            None,
        "question_text":
            None,
        "confidence":
            0.99,
        "language":
            "English",
        "metadata":
            {},
    },
)

machine.handle(
    context,
    coverage_event,
)

assert context.quote.coverage_type == "Both"
assert context.state == FlowState.QUOTE_TRAVEL

print("PASS 1 - semantic adapter -> normalizer -> state machine works end-to-end")


# ------------------------------------------------------------------
# Travel uncertain -> defer.
# ------------------------------------------------------------------

unclear_event = semantic_from_raw(
    context,
    {
        "action":
            "UNCLEAR",
        "field_name":
            None,
        "value":
            None,
        "question_type":
            None,
        "question_text":
            None,
        "confidence":
            0.93,
        "language":
            "English",
        "metadata":
            {},
    },
)

machine.handle(
    context,
    unclear_event,
)

assert context.deferred_fields == [
    "travel_required"
]
assert context.state == FlowState.QUOTE_DURATION

print("PASS 2 - semantic uncertainty defers current required field")


# ------------------------------------------------------------------
# Invalid Gemini output cannot mutate state.
# ------------------------------------------------------------------

before_state = context.state
before_quote = context.quote.as_dict()

try:
    semantic_from_raw(
        context,
        {
            "action":
                "FIELD_VALUE",
            "field_name":
                "location",
            "value":
                "London",
            "confidence":
                0.99,
            "language":
                "English",
            "metadata":
                {},
        },
    )
except Exception:
    pass
else:
    raise AssertionError(
        "Expected invalid semantic output to be rejected."
    )

assert context.state == before_state
assert context.quote.as_dict() == before_quote

print("PASS 3 - invalid Gemini output cannot mutate conversation context")

print()
print("=" * 72)
print("V3 BLOCK 3 PIPELINE INTEGRATION TEST PASSED")
print("=" * 72)
