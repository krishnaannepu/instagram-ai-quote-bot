from business_answer_service_v3 import BusinessAnswerServiceV3
from business_knowledge_adapter_v3 import BusinessKnowledgeAdapterV3
from business_question_coordinator_v3 import BusinessQuestionCoordinatorV3
from conversation_models import ConversationContext, FlowState
from conversation_orchestrator import ConversationOrchestrator
from response_plan import ResponseAction
from semantic_contract import SemanticAction, SemanticInterpretation


class FakeKnowledge:
    @staticmethod
    def get_business_knowledge(force_refresh=False):
        return {
            "pricing": [
                {
                    "service": "Wedding",
                    "package": "Basic",
                    "included_hours": 4,
                    "photography_price": "£500",
                    "videography_price": "£650",
                    "both_price": "£950",
                    "extra_hour_rate": "£80",
                    "travel_fee": "£0",
                },
                {
                    "service": "Wedding",
                    "package": "Premium",
                    "included_hours": 6,
                    "photography_price": "£700",
                    "videography_price": "£850",
                    "both_price": "£1,200",
                    "extra_hour_rate": "£100",
                    "travel_fee": "£0",
                },
                {
                    "service": "Birthday",
                    "package": "Basic",
                    "included_hours": 3,
                    "photography_price": "£250",
                    "videography_price": "£300",
                    "both_price": "£450",
                    "extra_hour_rate": "£50",
                    "travel_fee": "£0",
                },
            ],
            "packages": [
                {
                    "service": "Wedding",
                    "package": "Basic",
                },
                {
                    "service": "Wedding",
                    "package": "Premium",
                },
            ],
            "business_info": [],
            "faqs": [],
        }


class QueueInterpreter:
    def __init__(self, meanings):
        self.meanings = list(meanings)

    def interpret(self, context, message_text, **kwargs):
        return self.meanings.pop(0)


def meaning(
    action,
    *,
    field_name=None,
    value=None,
    question_type=None,
    question_text=None,
):
    return SemanticInterpretation(
        action=action,
        field_name=field_name,
        value=value,
        question_type=question_type,
        question_text=question_text,
        confidence=0.99,
        language="English",
    )


catalogue = BusinessKnowledgeAdapterV3(
    service_module=FakeKnowledge
)
catalogue_data = catalogue.get_catalogue()


# ------------------------------------------------------------------
# Regression 1: Wedding cannot become the package.
# ------------------------------------------------------------------

context = ConversationContext(
    state=FlowState.QUOTE_PACKAGE
)
context.quote.service = "Wedding"

orchestrator = ConversationOrchestrator(
    semantic_interpreter=QueueInterpreter(
        [
            meaning(
                SemanticAction.FIELD_VALUE,
                field_name="package",
                value="Wedding",
            )
        ]
    ),
    supported_services=catalogue_data["supported_services"],
    packages_by_service=catalogue_data["packages_by_service"],
)

result = orchestrator.handle_text(
    context=context,
    message_text="Wedding",
)

assert context.state == FlowState.QUOTE_PACKAGE
assert context.quote.service == "Wedding"
assert context.quote.package is None
assert result.event.type.value == "INVALID_FIELD_VALUE"
assert result.response_plan.action == ResponseAction.ASK_FIELD
assert result.response_plan.next_field == "package"
assert result.response_plan.options == [
    "Basic",
    "Premium",
]

print(
    "PASS 1 - Wedding cannot be accepted as a package or advance to coverage"
)


# ------------------------------------------------------------------
# Regression 2: known Wedding package comparison uses Wedding rows.
# ------------------------------------------------------------------

context = ConversationContext(
    state=FlowState.QUOTE_PACKAGE
)
context.quote.service = "Wedding"

orchestrator = ConversationOrchestrator(
    semantic_interpreter=QueueInterpreter(
        [
            meaning(
                SemanticAction.BUSINESS_QUESTION,
                question_type=None,
                question_text=(
                    "What's the difference between basic and premium"
                ),
            )
        ]
    ),
    supported_services=catalogue_data["supported_services"],
    packages_by_service=catalogue_data["packages_by_service"],
)

question_turn = orchestrator.handle_text(
    context=context,
    message_text=(
        "What's the difference between basic and premium"
    ),
)

assert context.state == FlowState.BUSINESS_INTERRUPT

answer_service = BusinessAnswerServiceV3(
    knowledge_adapter=catalogue,
    client=None,
)

coordinator = BusinessQuestionCoordinatorV3(
    orchestrator=orchestrator,
    answer_service=answer_service,
    quote_adapter=None,
)

resolution = coordinator.resolve(
    context=context,
    question_text=(
        question_turn.response_plan.business_question_text
        or ""
    ),
    question_type=(
        question_turn.response_plan.business_question_type
    ),
    customer_language="English",
)

answer = resolution.answer.answer_text or ""

assert context.state == FlowState.QUOTE_PACKAGE
assert "Wedding" in answer
assert "Basic:" in answer
assert "Premium:" in answer
assert "£500" in answer
assert "£700" in answer
assert "£950" in answer
assert "£1,200" in answer
assert "which service" not in answer.lower()
assert "service are you interested" not in answer.lower()
assert resolution.resume_plan.action == ResponseAction.RESUME_FIELD
assert resolution.resume_plan.next_field == "package"

print(
    "PASS 2 - Wedding package comparison is answered from Wedding Sheets rows"
)


# ------------------------------------------------------------------
# Regression 3: other service rows cannot leak into Wedding answer.
# ------------------------------------------------------------------

assert "£250" not in answer
assert "Birthday" not in answer

print(
    "PASS 3 - package comparison is scoped to the already-selected service"
)


print()
print("=" * 72)
print("V3 PRODUCTION DEFECT HOTFIX TEST PASSED")
print("=" * 72)
