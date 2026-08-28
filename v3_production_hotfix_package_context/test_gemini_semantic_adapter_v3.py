from conversation_models import ConversationContext, FlowState
from gemini_semantic_adapter import (
    GeminiSemanticAdapter,
    GeminiSemanticAdapterError,
)
from semantic_contract import SemanticAction


adapter = GeminiSemanticAdapter(
    client=object()
)


def parse(
    context,
    **kwargs,
):
    payload = {
        "action": kwargs.pop(
            "action"
        ),
        "field_name": kwargs.pop(
            "field_name",
            None,
        ),
        "value": kwargs.pop(
            "value",
            None,
        ),
        "question_type": kwargs.pop(
            "question_type",
            None,
        ),
        "question_text": kwargs.pop(
            "question_text",
            None,
        ),
        "confidence": kwargs.pop(
            "confidence",
            0.98,
        ),
        "language": kwargs.pop(
            "language",
            "English",
        ),
        "metadata": kwargs.pop(
            "metadata",
            {},
        ),
    }

    if kwargs:
        raise AssertionError(
            f"Unexpected test args: {kwargs}"
        )

    return adapter.parse_response(
        context=context,
        raw=payload,
    )


# ------------------------------------------------------------------
# TEST 1 - package choice while package state is authoritative
# ------------------------------------------------------------------

context = ConversationContext(
    state=FlowState.QUOTE_PACKAGE
)

result = parse(
    context,
    action="FIELD_VALUE",
    field_name="package",
    value="Basic",
)

assert result.action == SemanticAction.FIELD_VALUE
assert result.field_name == "package"
assert result.value == "Basic"

print("PASS 1 - package selection contract is state-specific")


# ------------------------------------------------------------------
# TEST 2 - wrong field cannot be returned for state
# ------------------------------------------------------------------

try:
    parse(
        context,
        action="FIELD_VALUE",
        field_name="coverage_type",
        value="Both",
    )
except GeminiSemanticAdapterError:
    pass
else:
    raise AssertionError(
        "Expected wrong FIELD_VALUE target to fail."
    )

print("PASS 2 - Gemini cannot target the wrong expected field")


# ------------------------------------------------------------------
# TEST 3 - bare Both contract while coverage is authoritative
# ------------------------------------------------------------------

context.state = FlowState.QUOTE_COVERAGE
context.quote.service = "Wedding"
context.quote.package = "Basic"

result = parse(
    context,
    action="FIELD_VALUE",
    field_name="coverage_type",
    value="Both",
)

assert result.action == SemanticAction.FIELD_VALUE
assert result.field_name == "coverage_type"
assert result.value == "Both"

print("PASS 3 - Both is constrained to coverage in QUOTE_COVERAGE")


# ------------------------------------------------------------------
# TEST 4 - package comparison after package selection becomes
# explicit reconsideration
# ------------------------------------------------------------------

result = parse(
    context,
    action="PACKAGE_RECONSIDERATION",
    question_type="PACKAGE_COMPARISON",
    question_text="Basic and Premium difference?",
)

assert (
    result.action
    == SemanticAction.PACKAGE_RECONSIDERATION
)

print("PASS 4 - package comparison can become reconsideration")


# ------------------------------------------------------------------
# TEST 5 - package question before selection remains business question
# ------------------------------------------------------------------

context = ConversationContext(
    state=FlowState.QUOTE_PACKAGE
)

result = parse(
    context,
    action="BUSINESS_QUESTION",
    question_type="PACKAGE_COMPARISON",
    question_text="Basic and Premium difference?",
)

assert result.action == SemanticAction.BUSINESS_QUESTION

print("PASS 5 - comparison before selection does not select/reconsider package")


# ------------------------------------------------------------------
# TEST 6 - package switch only valid inside reconfirmation
# ------------------------------------------------------------------

context = ConversationContext(
    state=FlowState.PACKAGE_RECONFIRMATION
)
context.quote.package = "Basic"

result = parse(
    context,
    action="SWITCH_PACKAGE",
    value="Premium",
)

assert result.action == SemanticAction.SWITCH_PACKAGE
assert result.value == "Premium"

print("PASS 6 - package switch contract is restricted to reconfirmation")


# ------------------------------------------------------------------
# TEST 7 - same switch outside reconfirmation is rejected
# ------------------------------------------------------------------

context.state = FlowState.QUOTE_COVERAGE

try:
    parse(
        context,
        action="SWITCH_PACKAGE",
        value="Premium",
    )
except GeminiSemanticAdapterError:
    pass
else:
    raise AssertionError(
        "SWITCH_PACKAGE must fail outside reconfirmation."
    )

print("PASS 7 - Gemini cannot bypass package reconfirmation state")


# ------------------------------------------------------------------
# TEST 8 - travel semantic field is strict
# ------------------------------------------------------------------

context = ConversationContext(
    state=FlowState.QUOTE_TRAVEL
)

result = parse(
    context,
    action="FIELD_VALUE",
    field_name="travel_required",
    value="Yes",
    language="Hinglish",
)

assert result.field_name == "travel_required"
assert result.value == "Yes"

print("PASS 8 - travel Yes contract is explicit, not inferred from location")


# ------------------------------------------------------------------
# TEST 9 - business question needs question text
# ------------------------------------------------------------------

context = ConversationContext(
    state=FlowState.QUOTE_DURATION
)

try:
    parse(
        context,
        action="BUSINESS_QUESTION",
    )
except GeminiSemanticAdapterError:
    pass
else:
    raise AssertionError(
        "BUSINESS_QUESTION without question_text must fail."
    )

print("PASS 9 - malformed business-question output is rejected")


# ------------------------------------------------------------------
# TEST 10 - invalid action for state is rejected
# ------------------------------------------------------------------

context = ConversationContext(
    state=FlowState.QUOTE_SERVICE
)

try:
    parse(
        context,
        action="KEEP_CURRENT_PACKAGE",
    )
except GeminiSemanticAdapterError:
    pass
else:
    raise AssertionError(
        "Invalid state/action combination must fail."
    )

print("PASS 10 - Gemini output must satisfy allowed action set")


# ------------------------------------------------------------------
# TEST 11 - prompt contains authoritative state and no mutation authority
# ------------------------------------------------------------------

context = ConversationContext(
    state=FlowState.QUOTE_COVERAGE
)
context.quote.service = "Wedding"
context.quote.package = "Basic"

request = type(
    "Request",
    (),
    {
        "state":
            context.state,
        "expected_field":
            context.expected_field(),
        "message_text":
            "both",
        "allowed_values":
            [
                "Photography",
                "Videography",
                "Both",
            ],
        "supported_services":
            [
                "Wedding",
                "Birthday",
            ],
        "packages_for_service":
            [
                "Basic",
                "Premium",
            ],
        "current_quote":
            context.quote.as_dict(),
        "current_package":
            "Basic",
        "deferred_fields":
            [],
    },
)()

prompt = adapter.build_prompt(
    request
)

assert "AUTHORITATIVE CURRENT STATE" in prompt
assert "QUOTE_COVERAGE" in prompt
assert "EXPECTED FIELD" in prompt
assert "coverage_type" in prompt
assert "You do NOT control conversation state." in prompt
assert "A bare \"both\" in QUOTE_COVERAGE must NEVER mean both packages." in prompt

print("PASS 11 - prompt explicitly constrains Gemini to interpretation only")

print()
print("=" * 72)
print("V3 BLOCK 3 GEMINI SEMANTIC CONTRACT TEST SUITE PASSED")
print("=" * 72)
