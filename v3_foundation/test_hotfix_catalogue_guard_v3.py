from conversation_models import ConversationContext, FlowState
from conversation_orchestrator import ConversationOrchestrator
from response_plan import ResponseAction
from semantic_contract import SemanticAction, SemanticInterpretation


class ScriptedInterpreter:
    def __init__(self, interpretation):
        self.interpretation = interpretation

    def interpret(self, context, message_text, **kwargs):
        return self.interpretation


def meaning(field_name, value):
    return SemanticInterpretation(
        action=SemanticAction.FIELD_VALUE,
        field_name=field_name,
        value=value,
        confidence=0.99,
        language="English",
    )


# ------------------------------------------------------------------
# 1. Exact production defect: Wedding must not become a package.
# ------------------------------------------------------------------
context = ConversationContext(
    state=FlowState.QUOTE_PACKAGE
)
context.quote.service = "Wedding"

orchestrator = ConversationOrchestrator(
    semantic_interpreter=ScriptedInterpreter(
        meaning("package", "Wedding")
    ),
    supported_services=[
        "Wedding",
        "Birthday",
        "Portrait",
        "Event",
    ],
    packages_by_service={
        "Wedding": ["Basic", "Premium"],
        "Birthday": ["Basic", "Premium"],
        "Portrait": ["Basic", "Premium"],
        "Event": ["Basic", "Premium"],
    },
)

result = orchestrator.handle_text(
    context=context,
    message_text="Wedding",
)

assert context.state == FlowState.QUOTE_PACKAGE
assert context.quote.package is None
assert result.event.type.value == "INVALID_FIELD_VALUE"
assert result.response_plan.action == ResponseAction.ASK_FIELD
assert result.response_plan.next_field == "package"
assert result.response_plan.options == ["Basic", "Premium"]

print("PASS 1 - Wedding cannot be accepted as a package")


# ------------------------------------------------------------------
# 2. Wrong service cannot enter service field.
# ------------------------------------------------------------------
context = ConversationContext(
    state=FlowState.QUOTE_SERVICE
)

orchestrator.semantic_interpreter = ScriptedInterpreter(
    meaning("service", "Premium")
)

result = orchestrator.handle_text(
    context=context,
    message_text="Premium",
)

assert context.state == FlowState.QUOTE_SERVICE
assert context.quote.service is None
assert result.event.type.value == "INVALID_FIELD_VALUE"
assert result.response_plan.options == [
    "Wedding",
    "Birthday",
    "Portrait",
    "Event",
]

print("PASS 2 - package name cannot be accepted as a service")


# ------------------------------------------------------------------
# 3. Wrong coverage cannot advance coverage state.
# ------------------------------------------------------------------
context = ConversationContext(
    state=FlowState.QUOTE_COVERAGE
)
context.quote.service = "Wedding"
context.quote.package = "Basic"

orchestrator.semantic_interpreter = ScriptedInterpreter(
    meaning("coverage_type", "Wedding")
)

result = orchestrator.handle_text(
    context=context,
    message_text="Wedding",
)

assert context.state == FlowState.QUOTE_COVERAGE
assert context.quote.coverage_type is None
assert result.event.type.value == "INVALID_FIELD_VALUE"
assert result.response_plan.options == [
    "Photography",
    "Videography",
    "Both",
]

print("PASS 3 - unrelated value cannot be accepted as coverage")


# ------------------------------------------------------------------
# 4. Valid package still progresses normally.
# ------------------------------------------------------------------
context = ConversationContext(
    state=FlowState.QUOTE_PACKAGE
)
context.quote.service = "Wedding"

orchestrator.semantic_interpreter = ScriptedInterpreter(
    meaning("package", "Premium")
)

result = orchestrator.handle_text(
    context=context,
    message_text="Premium",
)

assert context.quote.package == "Premium"
assert context.state == FlowState.QUOTE_COVERAGE
assert result.response_plan.next_field == "coverage_type"

print("PASS 4 - valid package still progresses to coverage")


# ------------------------------------------------------------------
# 5. Case differences are canonicalized by Python.
# ------------------------------------------------------------------
context = ConversationContext(
    state=FlowState.QUOTE_PACKAGE
)
context.quote.service = "Wedding"

orchestrator.semantic_interpreter = ScriptedInterpreter(
    meaning("package", "premium")
)

result = orchestrator.handle_text(
    context=context,
    message_text="premium",
)

assert context.quote.package == "Premium"
assert context.state == FlowState.QUOTE_COVERAGE

print("PASS 5 - valid value is canonicalized to approved catalogue spelling")

print()
print("=" * 72)
print("V3 PRODUCTION HOTFIX CATALOGUE GUARD TEST PASSED")
print("=" * 72)
