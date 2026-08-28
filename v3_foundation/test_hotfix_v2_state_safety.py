
from conversation_models import ConversationContext, FlowState
from conversation_orchestrator import ConversationOrchestrator
from semantic_contract import SemanticAction, SemanticInterpretation


class ScriptedInterpreter:
    def __init__(self, result):
        self.result = result

    def interpret(self, context, message_text, **kwargs):
        return self.result


def make_interpretation(action, field_name=None, value=None):
    return SemanticInterpretation(
        action=action,
        field_name=field_name,
        value=value,
        confidence=0.9,
        language="English",
    )


# Exact production failure: Gemini says UNCLEAR for "Wedding" while package is expected.
context = ConversationContext(state=FlowState.QUOTE_PACKAGE)
context.quote.service = "Wedding"

orch = ConversationOrchestrator(
    semantic_interpreter=ScriptedInterpreter(
        make_interpretation(SemanticAction.UNCLEAR)
    ),
    supported_services=["Wedding", "Birthday", "Portrait", "Event"],
    packages_by_service={
        "Wedding": ["Basic", "Premium"],
        "Birthday": ["Basic", "Premium"],
        "Portrait": ["Basic", "Premium"],
        "Event": ["Basic", "Premium"],
    },
)

result = orch.handle_text(
    context=context,
    message_text="Wedding",
)

assert context.state == FlowState.QUOTE_PACKAGE
assert context.quote.package is None
assert result.event.type.value == "INVALID_FIELD_VALUE"
assert result.response_plan.next_field == "package"
print("PASS 1 - UNCLEAR Wedding cannot defer package or advance to coverage")


# Wrong service value when service is expected.
context = ConversationContext(state=FlowState.QUOTE_SERVICE)
orch.semantic_interpreter = ScriptedInterpreter(
    make_interpretation(SemanticAction.UNCLEAR)
)
result = orch.handle_text(
    context=context,
    message_text="Premium",
)
assert context.state == FlowState.QUOTE_SERVICE
assert context.quote.service is None
assert result.event.type.value == "INVALID_FIELD_VALUE"
print("PASS 2 - package literal cannot advance service state")


# Gemini wrongly emits FIELD_VALUE package=Wedding.
context = ConversationContext(state=FlowState.QUOTE_PACKAGE)
context.quote.service = "Wedding"
orch.semantic_interpreter = ScriptedInterpreter(
    make_interpretation(
        SemanticAction.FIELD_VALUE,
        field_name="package",
        value="Wedding",
    )
)
result = orch.handle_text(
    context=context,
    message_text="Wedding please",
)
assert context.state == FlowState.QUOTE_PACKAGE
assert context.quote.package is None
assert result.event.type.value == "INVALID_FIELD_VALUE"
print("PASS 3 - invalid FIELD_VALUE is rejected by Python catalogue")


# Valid package must still work.
context = ConversationContext(state=FlowState.QUOTE_PACKAGE)
context.quote.service = "Wedding"
orch.semantic_interpreter = ScriptedInterpreter(
    make_interpretation(
        SemanticAction.FIELD_VALUE,
        field_name="package",
        value="basic",
    )
)
result = orch.handle_text(
    context=context,
    message_text="basic",
)
assert context.state == FlowState.QUOTE_COVERAGE
assert context.quote.package == "Basic"
print("PASS 4 - valid package canonicalizes and progresses")

print()
print("=" * 72)
print("V3 PRODUCTION HOTFIX V2 STATE SAFETY TEST PASSED")
print("=" * 72)
