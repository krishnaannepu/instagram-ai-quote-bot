from pathlib import Path

from conversation_models import (
    ConversationContext,
    FlowState,
)
from gemini_semantic_adapter import GeminiSemanticAdapter
from semantic_contract import SemanticAction


adapter = GeminiSemanticAdapter(
    client=object()
)

# Verify Block 4's important state prompts without making API calls.
cases = [
    (
        FlowState.QUOTE_COVERAGE,
        "coverage_type",
        "both",
        "A bare \"both\" in QUOTE_COVERAGE must NEVER mean both packages.",
    ),
    (
        FlowState.QUOTE_TRAVEL,
        "travel_required",
        "okay kardo",
        "Never infer from location.",
    ),
    (
        FlowState.PACKAGE_RECONFIRMATION,
        None,
        "premium kardo",
        "kept or switched",
    ),
]

for state, expected_field, message, required_text in cases:
    context = ConversationContext(
        state=state
    )

    context.quote.service = "Wedding"
    context.quote.package = "Basic"

    request = type(
        "SemanticRequestForTest",
        (),
        {
            "state":
                state,
            "expected_field":
                expected_field,
            "message_text":
                message,
            "allowed_values":
                [],
            "supported_services":
                [
                    "Wedding",
                    "Birthday",
                    "Portrait",
                    "Event",
                ],
            "packages_for_service":
                [
                    "Basic",
                    "Premium",
                ],
            "current_quote":
                context.quote.as_dict(),
            "current_package":
                context.quote.package,
            "deferred_fields":
                [],
        },
    )()

    prompt = adapter.build_prompt(
        request
    )

    assert state.value in prompt
    assert required_text in prompt

print(
    "PASS 1 - live smoke cases are backed by state-specific prompt guards"
)

# Invalid live-model output still gets blocked by Python.
context = ConversationContext(
    state=FlowState.QUOTE_COVERAGE
)

context.quote.service = "Wedding"
context.quote.package = "Basic"

try:
    adapter.parse_response(
        context=context,
        raw={
            "action":
                "FIELD_VALUE",
            "field_name":
                "package",
            "value":
                "Premium",
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
        "Wrong-field live output must be rejected."
    )

print(
    "PASS 2 - Python still rejects wrong-field Gemini output"
)

print()
print("=" * 72)
print("V3 BLOCK 4 OFFLINE SAFETY TEST PASSED")
print("=" * 72)
