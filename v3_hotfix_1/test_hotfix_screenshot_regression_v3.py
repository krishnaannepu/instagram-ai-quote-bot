from types import SimpleNamespace

from business_answer_service_v3 import BusinessAnswerServiceV3
from business_knowledge_adapter_v3 import BusinessKnowledgeAdapterV3
from business_question_coordinator_v3 import BusinessQuestionCoordinatorV3
from conversation_models import ConversationContext, FlowState
from conversation_orchestrator import ConversationOrchestrator
from customer_response_renderer_v3 import CustomerResponseRendererV3
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
                {
                    "service": "Birthday",
                    "package": "Basic",
                    "included_hours": 3,
                    "photography_price": 250,
                    "videography_price": 300,
                    "both_price": 450,
                    "extra_hour_rate": 50,
                    "travel_fee": 0,
                },
                {
                    "service": "Birthday",
                    "package": "Premium",
                    "included_hours": 4,
                    "photography_price": 350,
                    "videography_price": 425,
                    "both_price": 600,
                    "extra_hour_rate": 60,
                    "travel_fee": 0,
                },
            ],
            "packages": [
                {
                    "service": "Wedding",
                    "package": "Basic",
                    "description": "Wedding Basic",
                },
                {
                    "service": "Wedding",
                    "package": "Premium",
                    "description": "Wedding Premium",
                },
                {
                    "service": "Birthday",
                    "package": "Basic",
                    "description": "Birthday Basic",
                },
                {
                    "service": "Birthday",
                    "package": "Premium",
                    "description": "Birthday Premium",
                },
            ],
            "business_info": [],
            "faqs": [],
        }


class FailIfGeminiCalled:
    class Models:
        @staticmethod
        def generate_content(**kwargs):
            raise AssertionError(
                "Gemini must not be used for a core package comparison."
            )

    models = Models()


class CapturingModels:
    def __init__(self):
        self.last_prompt = ""

    def generate_content(self, **kwargs):
        self.last_prompt = kwargs["contents"]
        return SimpleNamespace(
            parsed={
                "answer_found": True,
                "answer_text": "Wedding Premium details.",
                "should_offer_human": False,
                "language": "English",
            },
            text=None,
        )


class CapturingClient:
    def __init__(self):
        self.models = CapturingModels()


class QueueInterpreter:
    def __init__(self, meanings):
        self.meanings = list(meanings)

    def interpret(self, context, message_text, **kwargs):
        if not self.meanings:
            raise AssertionError(
                f"No scripted semantic result for {message_text!r}"
            )
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


knowledge = BusinessKnowledgeAdapterV3(
    service_module=FakeKnowledge
)
catalogue = knowledge.get_catalogue()

interpreter = QueueInterpreter(
    [
        meaning(
            SemanticAction.FIELD_VALUE,
            field_name="service",
            value="Wedding",
        ),
        meaning(
            SemanticAction.BUSINESS_QUESTION,
            question_text=(
                "What's the difference between basic and premium"
            ),
        ),
        # Reproduce the exact bad Gemini output seen in production:
        # package field, but value Wedding.
        meaning(
            SemanticAction.FIELD_VALUE,
            field_name="package",
            value="Wedding",
        ),
        meaning(
            SemanticAction.FIELD_VALUE,
            field_name="package",
            value="Basic",
        ),
        meaning(
            SemanticAction.PACKAGE_RECONSIDERATION,
            question_type="PACKAGE_COMPARISON",
            question_text=(
                "What's the difference between basic and premium"
            ),
        ),
    ]
)

orchestrator = ConversationOrchestrator(
    semantic_interpreter=interpreter,
    supported_services=catalogue["supported_services"],
    packages_by_service=catalogue["packages_by_service"],
)

answer_service = BusinessAnswerServiceV3(
    knowledge_adapter=knowledge,
    client=FailIfGeminiCalled(),
)

coordinator = BusinessQuestionCoordinatorV3(
    orchestrator=orchestrator,
    answer_service=answer_service,
    quote_adapter=None,
)

renderer = CustomerResponseRendererV3()
context = ConversationContext()

orchestrator.handle_button(
    context=context,
    payload="GET_QUOTE",
)

orchestrator.handle_text(
    context=context,
    message_text="Wedding",
)

assert context.state == FlowState.QUOTE_PACKAGE
assert context.quote.service == "Wedding"

print("PASS 1 - Wedding remains the authoritative selected service")

question_turn = orchestrator.handle_text(
    context=context,
    message_text=(
        "What's the difference between basic and premium"
    ),
)

assert context.state == FlowState.BUSINESS_INTERRUPT

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

answer_text = resolution.answer.answer_text or ""

assert context.state == FlowState.QUOTE_PACKAGE
assert "For Wedding" in answer_text
assert "Basic: up to 4 hours" in answer_text
assert "Premium: up to 6 hours" in answer_text
assert "£500" in answer_text
assert "£1,200" in answer_text
assert "Birthday" not in answer_text
assert "which service" not in answer_text.lower()
assert "service you have in mind" not in answer_text.lower()

print(
    "PASS 2 - package comparison before package selection uses exact Wedding data"
)

invalid_turn = orchestrator.handle_text(
    context=context,
    message_text="Wedding",
)

assert context.state == FlowState.QUOTE_PACKAGE
assert context.quote.package is None
assert invalid_turn.event.type.value == "INVALID_FIELD_VALUE"
assert invalid_turn.response_plan.options == [
    "Basic",
    "Premium",
]

invalid_message = renderer.render_plan(
    invalid_turn.response_plan
)

assert "Basic or Premium" in invalid_message.text

print(
    "PASS 3 - Wedding can never be written into the package field or advance state"
)

basic_turn = orchestrator.handle_text(
    context=context,
    message_text="Basic",
)

assert context.quote.package == "Basic"
assert context.state == FlowState.QUOTE_COVERAGE

print("PASS 4 - a valid package still advances normally")

reconsider_turn = orchestrator.handle_text(
    context=context,
    message_text=(
        "What's the difference between basic and premium"
    ),
)

assert context.state == FlowState.PACKAGE_RECONFIRMATION

reconsider_resolution = coordinator.resolve_package_reconsideration(
    context=context,
    question_text=(
        reconsider_turn.response_plan.business_question_text
        or ""
    ),
    question_type=(
        reconsider_turn.response_plan.business_question_type
    ),
    customer_language="English",
)

assert "For Wedding" in (
    reconsider_resolution.answer.answer_text
    or ""
)
assert reconsider_resolution.resume_plan.current_package == "Basic"
assert context.quote.package == "Basic"

print(
    "PASS 5 - comparison after Basic selection answers Wedding data then reconfirms package"
)

# General package information that is not a Basic-vs-Premium comparison still
# uses Gemini, but only receives the already-selected service rows.
capturing_client = CapturingClient()
filtered_answer_service = BusinessAnswerServiceV3(
    knowledge_adapter=knowledge,
    client=capturing_client,
)

context2 = ConversationContext(
    state=FlowState.QUOTE_PACKAGE
)
context2.quote.service = "Wedding"

filtered_answer_service.answer(
    context=context2,
    question_text="What does Premium include?",
    question_type="PACKAGE_INFO",
    customer_language="English",
)

prompt = capturing_client.models.last_prompt

assert "CURRENT SELECTED SERVICE\nWedding" in prompt
assert '"service": "Wedding"' in prompt
assert '"service": "Birthday"' not in prompt
assert "Never ask which service" in prompt

print(
    "PASS 6 - non-comparison package questions are grounded only to selected service"
)

print()
print("=" * 72)
print("V3 PRODUCTION HOTFIX 1 SCREENSHOT REGRESSION PASSED")
print("=" * 72)
