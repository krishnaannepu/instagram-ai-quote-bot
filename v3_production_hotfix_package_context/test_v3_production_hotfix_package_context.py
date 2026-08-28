from types import SimpleNamespace

from business_answer_service_v3 import BusinessAnswerServiceV3
from business_knowledge_adapter_v3 import BusinessKnowledgeAdapterV3
from business_question_coordinator_v3 import BusinessQuestionCoordinatorV3
from conversation_models import ConversationContext, FlowState
from conversation_orchestrator import ConversationOrchestrator
from response_plan import ResponseAction
from semantic_contract import SemanticAction, SemanticInterpretation


class FakeKnowledgeModule:
    @staticmethod
    def get_business_knowledge(force_refresh=False):
        return {
            "pricing": [
                {
                    "service": "Wedding",
                    "package": "Basic",
                    "included_hours": 4,
                    "photography_price": 500,
                    "videography_price": 650,
                    "both_price": 950,
                    "extra_hour_rate": 80,
                    "travel_fee": 0,
                },
                {
                    "service": "Wedding",
                    "package": "Premium",
                    "included_hours": 6,
                    "photography_price": 700,
                    "videography_price": 850,
                    "both_price": 1200,
                    "extra_hour_rate": 100,
                    "travel_fee": 0,
                },
            ],
            "packages": [
                {"service": "Wedding", "package": "Basic"},
                {"service": "Wedding", "package": "Premium"},
            ],
            "business_info": [],
            "faqs": [],
        }


class MustNotBeCalledModels:
    def generate_content(self, **kwargs):
        raise AssertionError(
            "Gemini business-answer generation must not be used for a "
            "known-service Basic/Premium comparison."
        )


class MustNotBeCalledClient:
    models = MustNotBeCalledModels()


class QueueInterpreter:
    def __init__(self, values):
        self.values = list(values)

    def interpret(self, context, message_text, **kwargs):
        if not self.values:
            raise AssertionError("No scripted semantic result remains.")
        return self.values.pop(0)


def meaning(action, *, field_name=None, value=None, question_type=None, question_text=None):
    return SemanticInterpretation(
        action=action,
        field_name=field_name,
        value=value,
        question_type=question_type,
        question_text=question_text,
        confidence=0.99,
        language="English",
    )


knowledge = BusinessKnowledgeAdapterV3(
    service_module=FakeKnowledgeModule
)
catalogue = knowledge.get_catalogue()

# ------------------------------------------------------------------
# 1. The exact production defect: Wedding cannot become package.
# ------------------------------------------------------------------
context = ConversationContext(state=FlowState.QUOTE_PACKAGE)
context.quote.service = "Wedding"

orchestrator = ConversationOrchestrator(
    semantic_interpreter=QueueInterpreter([
        meaning(
            SemanticAction.FIELD_VALUE,
            field_name="package",
            value="Wedding",
        )
    ]),
    supported_services=catalogue["supported_services"],
    packages_by_service=catalogue["packages_by_service"],
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
# 2. Valid package still advances normally.
# ------------------------------------------------------------------
orchestrator.semantic_interpreter = QueueInterpreter([
    meaning(
        SemanticAction.FIELD_VALUE,
        field_name="package",
        value="basic",  # lower-case model output is canonicalized by Python
    )
])

result = orchestrator.handle_text(
    context=context,
    message_text="Basic",
)

assert context.quote.package == "Basic"
assert context.state == FlowState.QUOTE_COVERAGE

print("PASS 2 - valid Basic package advances and is canonicalized")


# ------------------------------------------------------------------
# 3. Known Wedding service + package question uses exact Wedding data.
# ------------------------------------------------------------------
context2 = ConversationContext(state=FlowState.QUOTE_PACKAGE)
context2.quote.service = "Wedding"

orchestrator2 = ConversationOrchestrator(
    semantic_interpreter=QueueInterpreter([
        meaning(
            SemanticAction.BUSINESS_QUESTION,
            question_type="PACKAGE_COMPARISON",
            question_text="What's the difference between Basic and Premium?",
        )
    ]),
    supported_services=catalogue["supported_services"],
    packages_by_service=catalogue["packages_by_service"],
)

answer_service = BusinessAnswerServiceV3(
    knowledge_adapter=knowledge,
    client=MustNotBeCalledClient(),
)

coordinator = BusinessQuestionCoordinatorV3(
    orchestrator=orchestrator2,
    answer_service=answer_service,
    quote_adapter=None,
)

turn = orchestrator2.handle_text(
    context=context2,
    message_text="What's the difference between Basic and Premium?",
)

assert context2.state == FlowState.BUSINESS_INTERRUPT

resolution = coordinator.resolve(
    context=context2,
    question_text=turn.response_plan.business_question_text,
    question_type=turn.response_plan.business_question_type,
    customer_language="English",
)

answer = resolution.answer.answer_text

assert "Wedding" in answer
assert "Basic" in answer
assert "Premium" in answer
assert "£500" in answer
assert "£650" in answer
assert "£950" in answer
assert "£700" in answer
assert "£850" in answer
assert "£1200" in answer
assert "£80 per hour" in answer
assert "£100 per hour" in answer
assert "which service" not in answer.lower()
assert context2.state == FlowState.QUOTE_PACKAGE
assert resolution.resume_plan.next_field == "package"

print("PASS 3 - Wedding package comparison is deterministic and service-aware")


# ------------------------------------------------------------------
# 4. After Basic is selected, comparison preserves package then reconfirms.
# ------------------------------------------------------------------
context3 = ConversationContext(state=FlowState.QUOTE_COVERAGE)
context3.quote.service = "Wedding"
context3.quote.package = "Basic"

orchestrator3 = ConversationOrchestrator(
    semantic_interpreter=QueueInterpreter([
        meaning(
            SemanticAction.PACKAGE_RECONSIDERATION,
            question_type="PACKAGE_COMPARISON_WITH_PRICING",
            question_text="What's the difference between Basic and Premium?",
        )
    ]),
    supported_services=catalogue["supported_services"],
    packages_by_service=catalogue["packages_by_service"],
)

coordinator3 = BusinessQuestionCoordinatorV3(
    orchestrator=orchestrator3,
    answer_service=answer_service,
    quote_adapter=None,
)

turn = orchestrator3.handle_text(
    context=context3,
    message_text="What's the difference between Basic and Premium?",
)

assert context3.state == FlowState.PACKAGE_RECONFIRMATION
assert context3.quote.package == "Basic"

resolution = coordinator3.resolve_package_reconsideration(
    context=context3,
    question_text=turn.response_plan.business_question_text,
    question_type=turn.response_plan.business_question_type,
    customer_language="English",
)

assert "£950" in resolution.answer.answer_text
assert "£1200" in resolution.answer.answer_text
assert context3.quote.package == "Basic"
assert resolution.resume_plan.action == ResponseAction.ASK_PACKAGE_RECONFIRMATION

print("PASS 4 - selected package is preserved while exact comparison is answered")

print()
print("=" * 72)
print("V3 PRODUCTION HOTFIX PACKAGE CONTEXT TEST PASSED")
print("=" * 72)
