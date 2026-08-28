from conversation_models import ConversationContext, FlowState
from event_normalizer import EventNormalizer, EventNormalizationError
from gemini_semantic_adapter import GeminiSemanticAdapter
from semantic_contract import SemanticAction


adapter = GeminiSemanticAdapter(
    client=object()
)
normalizer = EventNormalizer()


def parse_and_normalize(
    context,
    raw,
):
    interpretation = adapter.parse_response(
        context=context,
        raw=raw,
    )
    return (
        interpretation,
        normalizer.from_semantic(
            context=context,
            interpretation=interpretation,
        ),
    )


context = ConversationContext(
    state=FlowState.POST_QUOTE
)

interpretation, event = parse_and_normalize(
    context,
    {
        "action": "SPEAK_TO_TEAM",
        "field_name": None,
        "value": None,
        "question_type": None,
        "question_text": None,
        "confidence": 0.99,
        "language": "English",
        "metadata": {},
    },
)

assert interpretation.action == SemanticAction.SPEAK_TO_TEAM
assert event.type.value == "SPEAK_TO_TEAM"

print("PASS 1 - natural handoff meaning maps to SPEAK_TO_TEAM event")


context = ConversationContext(
    state=FlowState.QUOTE_COVERAGE
)
context.quote.service = "Wedding"
context.quote.package = "Basic"

interpretation, event = parse_and_normalize(
    context,
    {
        "action": "REQUEST_CALLBACK",
        "field_name": None,
        "value": None,
        "question_type": None,
        "question_text": None,
        "confidence": 0.98,
        "language": "Hinglish",
        "metadata": {},
    },
)

assert interpretation.action == SemanticAction.REQUEST_CALLBACK
assert event.type.value == "REQUEST_CALLBACK"

print("PASS 2 - callback request can interrupt an active quote")


context = ConversationContext(
    state=FlowState.CALLBACK_PREFERENCE
)

interpretation, event = parse_and_normalize(
    context,
    {
        "action": "CALLBACK_PREFERENCE_VALUE",
        "field_name": None,
        "value": "Morning",
        "question_type": None,
        "question_text": None,
        "confidence": 0.99,
        "language": "Hindi",
        "metadata": {},
    },
)

assert event.type.value == "CALLBACK_PREFERENCE_VALUE"
assert event.value == "Morning"

print("PASS 3 - callback preference semantic value is canonical")


try:
    parse_and_normalize(
        context,
        {
            "action": "CALLBACK_PREFERENCE_VALUE",
            "field_name": None,
            "value": "Evening",
            "question_type": None,
            "question_text": None,
            "confidence": 0.99,
            "language": "English",
            "metadata": {},
        },
    )
except EventNormalizationError:
    pass
else:
    raise AssertionError(
        "Unsupported callback preference should be rejected."
    )

print("PASS 4 - unsupported callback preference cannot enter state machine")

print()
print("=" * 72)
print("V3 BLOCK 10 HANDOFF SEMANTIC CONTRACT TEST PASSED")
print("=" * 72)
