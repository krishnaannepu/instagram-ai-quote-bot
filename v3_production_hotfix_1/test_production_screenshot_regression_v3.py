from types import SimpleNamespace

from business_answer_service_v3 import BusinessAnswerServiceV3
from business_knowledge_adapter_v3 import BusinessKnowledgeAdapterV3
from business_question_coordinator_v3 import BusinessQuestionCoordinatorV3
from conversation_events import ConversationEvent, EventType
from conversation_models import ConversationContext, FlowState
from conversation_orchestrator import ConversationOrchestrator
from customer_response_renderer_v3 import CustomerResponseRendererV3
from quote_adapter_v3 import QuoteAdapterV3
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
            ],
            "packages": [
                {
                    "service": "Wedding",
                    "package": "Basic",
                    "description": "Standard professional editing and digital delivery.",
                },
                {
                    "service": "Wedding",
                    "package": "Premium",
                    "description": "Enhanced professional editing and priority handling.",
                },
            ],
            "business_info": [],
            "faqs": [],
        }


class NeverCallModels:
    def generate_content(self, **kwargs):
        raise AssertionError(
            "Gemini business-answer generation must not be used for "
            "a package comparison when the service is already known."
        )


class NeverCallClient:
    models = NeverCallModels()


class QueueInterpreter:
    def __init__(self, meanings):
        self.meanings = list(meanings)

    def interpret(self, context, message_text, **kwargs):
        if not self.meanings:
            raise AssertionError(
                f"No scripted interpretation remains for {message_text!r}"
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
            question_type=None,
            question_text="What's the difference between basic and premium",
        ),
        # This reproduces the production defect: the model labels Wedding as
        # the expected package field. Python must reject the VALUE.
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
            question_type=None,
            question_text="What's the difference between basic and premium",
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
    client=NeverCallClient(),
)

coordinator = BusinessQuestionCoordinatorV3(
    orchestrator=orchestrator,
    answer_service=answer_service,
    quote_adapter=None,
)

renderer = CustomerResponseRendererV3()
context = ConversationContext()


# ------------------------------------------------------------------
# 1. Wedding service is selected.
# ------------------------------------------------------------------

orchestrator.handle_button(
    context=context,
    payload="GET_QUOTE",
)

service_turn = orchestrator.handle_text(
    context=context,
    message_text="Wedding",
)

assert context.state == FlowState.QUOTE_PACKAGE
assert context.quote.service == "Wedding"
assert context.quote.package is None
assert service_turn.response_plan.next_field == "package"

print("PASS 1 - Wedding remains the selected service at package state")


# ------------------------------------------------------------------
# 2. Package comparison before package selection uses Wedding facts.
# ------------------------------------------------------------------

question_turn = orchestrator.handle_text(
    context=context,
    message_text="What's the difference between basic and premium",
)

assert context.state == FlowState.BUSINESS_INTERRUPT

resolution = coordinator.resolve(
    context=context,
    question_text=question_turn.response_plan.business_question_text,
    question_type=question_turn.response_plan.business_question_type,
    customer_language="English",
)

assert context.state == FlowState.QUOTE_PACKAGE

answer = resolution.answer.answer_text or ""

assert "For Wedding" in answer
assert "Basic:" in answer
assert "Premium:" in answer
assert "Photography: £500" in answer
assert "Videography: £650" in answer
assert "Both: £950" in answer
assert "Photography: £700" in answer
assert "Videography: £850" in answer
assert "Both: £1200" in answer
assert "which service" not in answer.lower()

assert resolution.resume_plan.next_field == "package"

print(
    "PASS 2 - Basic/Premium question uses exact Wedding Sheets facts and "
    "returns to package selection"
)


# ------------------------------------------------------------------
# 3. Wedding can NEVER be accepted as a package.
# ------------------------------------------------------------------

bad_package_turn = orchestrator.handle_text(
    context=context,
    message_text="Wedding",
)

assert bad_package_turn.event.type == EventType.INVALID_FIELD_VALUE
assert context.state == FlowState.QUOTE_PACKAGE
assert context.quote.service == "Wedding"
assert context.quote.package is None

bad_package_message = renderer.render_plan(
    bad_package_turn.response_plan
)

assert "not an available package" in bad_package_message.text
assert "Basic, Premium" in bad_package_message.text

print(
    "PASS 3 - Wedding is rejected by Python as a package and state does not advance"
)


# ------------------------------------------------------------------
# 4. A real package still progresses normally.
# ------------------------------------------------------------------

valid_package_turn = orchestrator.handle_text(
    context=context,
    message_text="Basic",
)

assert context.quote.package == "Basic"
assert context.state == FlowState.QUOTE_COVERAGE
assert valid_package_turn.response_plan.next_field == "coverage_type"

print("PASS 4 - Basic is accepted and coverage becomes authoritative")


# ------------------------------------------------------------------
# 5. Comparison after Basic selection answers Wedding facts first, then
#    asks keep/switch, preserving Basic.
# ------------------------------------------------------------------

reconsider = orchestrator.handle_text(
    context=context,
    message_text="What's the difference between basic and premium",
)

assert context.state == FlowState.PACKAGE_RECONFIRMATION
assert context.quote.package == "Basic"

reconsider_resolution = coordinator.resolve_package_reconsideration(
    context=context,
    question_text=reconsider.response_plan.business_question_text,
    question_type=reconsider.response_plan.business_question_type,
    customer_language="English",
)

comparison_answer = reconsider_resolution.answer.answer_text or ""

assert "For Wedding" in comparison_answer
assert "Basic:" in comparison_answer
assert "Premium:" in comparison_answer
assert context.quote.package == "Basic"
assert reconsider_resolution.resume_plan.current_package == "Basic"

reconfirm_message = renderer.render_plan(
    reconsider_resolution.resume_plan
)

assert "Basic selected" in reconfirm_message.text
assert "continue with Basic" in reconfirm_message.text

print(
    "PASS 5 - comparison after Basic selection answers exact facts before keep/switch"
)


print()
print("=" * 72)
print("V3 PRODUCTION SCREENSHOT REGRESSION TEST PASSED")
print("=" * 72)
