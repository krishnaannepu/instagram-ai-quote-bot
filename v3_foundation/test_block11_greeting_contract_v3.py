from conversation_models import ConversationContext, FlowState
from event_normalizer import EventNormalizer
from gemini_semantic_adapter import GeminiSemanticAdapter
from semantic_contract import SemanticAction


adapter = GeminiSemanticAdapter(
    client=object()
)

context = ConversationContext(
    state=FlowState.IDLE
)

interpretation = adapter.parse_response(
    context=context,
    raw={
        "action": "GREETING",
        "field_name": None,
        "value": None,
        "question_type": None,
        "question_text": None,
        "confidence": 0.99,
        "language": "English",
        "metadata": {},
    },
)

assert interpretation.action == SemanticAction.GREETING

event = EventNormalizer().from_semantic(
    context=context,
    interpretation=interpretation,
)

assert event.type.value == "GREETING"

print("PASS 1 - Gemini GREETING contract is valid only through V3 semantic boundary")


prompt = adapter.build_prompt(
    __import__(
        "gemini_semantic_adapter"
    ).SemanticRequest(
        state=FlowState.IDLE,
        expected_field=None,
        message_text="Hi",
        allowed_values=[],
        supported_services=[
            "Wedding",
            "Birthday",
            "Portrait",
            "Event",
        ],
        packages_for_service=[],
        current_quote=context.quote.as_dict(),
        current_package=None,
        deferred_fields=[],
    )
)

assert "simple greetings" in prompt
assert "GREETING" in prompt
assert "substantive business question" in prompt

print("PASS 2 - Gemini prompt distinguishes greeting from real customer intent")

print()
print("=" * 72)
print("V3 BLOCK 11 GREETING SEMANTIC CONTRACT TEST PASSED")
print("=" * 72)
