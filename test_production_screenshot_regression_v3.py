"""
V3 production screenshot regression.

Reproduces the exact Instagram conversation from the first production
acceptance screenshot. Fully offline: fake Sheets knowledge, a scripted
semantic interpreter, and a Gemini client that raises if it is ever called.

Assertions deliberately check FACTS AND STATE, never marketing wording.
Asserting on exact sentences is what produced repeated phantom failures.
"""

from business_answer_service_v3 import BusinessAnswerServiceV3
from business_knowledge_adapter_v3 import BusinessKnowledgeAdapterV3
from business_question_coordinator_v3 import BusinessQuestionCoordinatorV3
from conversation_events import EventType
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
            "Gemini must not generate package facts when the service "
            "is already known to Python."
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


def meaning(action, *, field_name=None, value=None,
            question_type=None, question_text=None):
    return SemanticInterpretation(
        action=action,
        field_name=field_name,
        value=value,
        question_type=question_type,
        question_text=question_text,
        confidence=0.99,
        language="English",
    )


COMPARISON = "What's the difference between basic and premium"

knowledge = BusinessKnowledgeAdapterV3(service_module=FakeKnowledge)
catalogue = knowledge.get_catalogue()

interpreter = QueueInterpreter([
    meaning(SemanticAction.FIELD_VALUE, field_name="service", value="Wedding"),
    meaning(SemanticAction.BUSINESS_QUESTION, question_text=COMPARISON),
    # The production defect: the model labels "Wedding" as the package.
    meaning(SemanticAction.FIELD_VALUE, field_name="package", value="Wedding"),
    meaning(SemanticAction.FIELD_VALUE, field_name="package", value="Basic"),
    meaning(SemanticAction.PACKAGE_RECONSIDERATION, question_text=COMPARISON),
])

orchestrator = ConversationOrchestrator(
    semantic_interpreter=interpreter,
    supported_services=catalogue["supported_services"],
    packages_by_service=catalogue["packages_by_service"],
)

coordinator = BusinessQuestionCoordinatorV3(
    orchestrator=orchestrator,
    answer_service=BusinessAnswerServiceV3(
        knowledge_adapter=knowledge,
        client=NeverCallClient(),
    ),
    quote_adapter=None,
)

renderer = CustomerResponseRendererV3()
context = ConversationContext()

WEDDING_FACTS = ["500", "650", "950", "700", "850", "1200"]


def assert_wedding_package_facts(answer: str, label: str):
    assert "Wedding" in answer, f"{label}: service name missing"
    assert "Basic" in answer, f"{label}: Basic missing"
    assert "Premium" in answer, f"{label}: Premium missing"
    for amount in WEDDING_FACTS:
        assert amount in answer, f"{label}: price {amount} missing"
    assert "which service" not in answer.lower(), (
        f"{label}: asked for a service Python already knows"
    )


# 1 -----------------------------------------------------------------
orchestrator.handle_button(context=context, payload="GET_QUOTE")
service_turn = orchestrator.handle_text(context=context, message_text="Wedding")

assert context.state == FlowState.QUOTE_PACKAGE
assert context.quote.service == "Wedding"
assert context.quote.package is None
assert service_turn.response_plan.next_field == "package"
print("PASS 1 - Wedding is held as the service and package is now expected")


# 2 -----------------------------------------------------------------
question_turn = orchestrator.handle_text(context=context, message_text=COMPARISON)
assert context.state == FlowState.BUSINESS_INTERRUPT

resolution = coordinator.resolve(
    context=context,
    question_text=question_turn.response_plan.business_question_text,
    question_type=question_turn.response_plan.business_question_type,
    customer_language="English",
)

assert context.state == FlowState.QUOTE_PACKAGE
assert_wedding_package_facts(resolution.answer.answer_text or "", "PASS 2")
assert resolution.resume_plan.next_field == "package"
print("PASS 2 - comparison answers exact Wedding facts and returns to package")


# 3 -----------------------------------------------------------------
bad_turn = orchestrator.handle_text(context=context, message_text="Wedding")

assert bad_turn.event.type == EventType.INVALID_FIELD_VALUE
assert context.state == FlowState.QUOTE_PACKAGE
assert context.quote.service == "Wedding"
assert context.quote.package is None

rejection = renderer.render_plan(bad_turn.response_plan).text
assert "Wedding" in rejection, "rejection must name the value it rejected"
assert "Basic" in rejection and "Premium" in rejection, (
    "rejection must list the allowed packages"
)
print("PASS 3 - Wedding is rejected as a package and the customer is told why")


# 4 -----------------------------------------------------------------
good_turn = orchestrator.handle_text(context=context, message_text="Basic")

assert context.quote.package == "Basic"
assert context.state == FlowState.QUOTE_COVERAGE
assert good_turn.response_plan.next_field == "coverage_type"
print("PASS 4 - Basic is accepted and coverage becomes the expected field")


# 5 -----------------------------------------------------------------
reconsider = orchestrator.handle_text(context=context, message_text=COMPARISON)
assert context.state == FlowState.PACKAGE_RECONFIRMATION
assert context.quote.package == "Basic"

reconsider_resolution = coordinator.resolve_package_reconsideration(
    context=context,
    question_text=reconsider.response_plan.business_question_text,
    question_type=reconsider.response_plan.business_question_type,
    customer_language="English",
)

assert_wedding_package_facts(
    reconsider_resolution.answer.answer_text or "", "PASS 5"
)
assert context.quote.package == "Basic", "comparison must not change the package"
assert reconsider_resolution.resume_plan.current_package == "Basic"

reconfirm = renderer.render_plan(reconsider_resolution.resume_plan).text
assert "Basic" in reconfirm, "keep/switch prompt must name the current package"
print("PASS 5 - comparison keeps Basic and asks keep/switch")


print()
print("=" * 72)
print("V3 PRODUCTION SCREENSHOT REGRESSION PASSED")
print("=" * 72)
