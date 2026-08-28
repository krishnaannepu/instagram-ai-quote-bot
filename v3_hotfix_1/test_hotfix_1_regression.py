from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(1, str(PROJECT_ROOT))

from types import SimpleNamespace

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


class MustNotCallModels:
    def generate_content(self, **kwargs):
        raise AssertionError(
            "Gemini business-answer generation must not be used for a "
            "service-known Basic/Premium comparison."
        )


class MustNotCallClient:
    models = MustNotCallModels()


class QueueInterpreter:
    def __init__(self, meanings):
        self.meanings = list(meanings)
        self.calls = []

    def interpret(self, context, message_text, **kwargs):
        self.calls.append(message_text)
        if not self.meanings:
            raise AssertionError(f"No semantic result scripted for {message_text!r}")
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
answer_service = BusinessAnswerServiceV3(
    knowledge_adapter=knowledge,
    client=MustNotCallClient(),
)


# ------------------------------------------------------------------
# 1. Exact screenshot defect: service already known, package comparison asked.
# ------------------------------------------------------------------

interpreter = QueueInterpreter(
    [
        meaning(
            SemanticAction.BUSINESS_QUESTION,
            question_type=None,
            question_text="What's the difference between basic and premium",
        ),
        meaning(
            SemanticAction.FIELD_VALUE,
            field_name="package",
            value="Basic",
        ),
    ]
)

orchestrator = ConversationOrchestrator(
    semantic_interpreter=interpreter,
    supported_services=catalogue["supported_services"],
    packages_by_service=catalogue["packages_by_service"],
)

coordinator = BusinessQuestionCoordinatorV3(
    orchestrator=orchestrator,
    answer_service=answer_service,
    quote_adapter=None,
)

context = ConversationContext(
    state=FlowState.QUOTE_PACKAGE
)
context.quote.service = "Wedding"

question_turn = orchestrator.handle_text(
    context=context,
    message_text="What's the difference between basic and premium",
)

assert context.state == FlowState.BUSINESS_INTERRUPT
assert question_turn.response_plan.action == ResponseAction.ANSWER_BUSINESS_QUESTION

resolution = coordinator.resolve(
    context=context,
    question_text=question_turn.response_plan.business_question_text or "",
    question_type=question_turn.response_plan.business_question_type,
    customer_language="English",
)

answer = resolution.answer.answer_text or ""

assert context.state == FlowState.QUOTE_PACKAGE
assert "Wedding" in answer
assert "Basic:" in answer
assert "Premium:" in answer
assert "£500" in answer
assert "£950" in answer
assert "£1,200" in answer
assert "Up to 4 hours" in answer
assert "Up to 6 hours" in answer
assert resolution.resume_plan.next_field == "package"

print(
    "PASS 1 - known Wedding service produces exact Basic/Premium Sheets comparison"
)


# ------------------------------------------------------------------
# 2. Exact screenshot defect: Wedding cannot be stored as package.
#    This must be rejected before Gemini is even called.
# ------------------------------------------------------------------

calls_before = len(interpreter.calls)

wrong_package = orchestrator.handle_text(
    context=context,
    message_text="Wedding",
)

assert len(interpreter.calls) == calls_before
assert wrong_package.event.type.value == "INVALID_FIELD_VALUE"
assert context.state == FlowState.QUOTE_PACKAGE
assert context.quote.package is None
assert wrong_package.response_plan.action == ResponseAction.ASK_FIELD
assert wrong_package.response_plan.next_field == "package"
assert wrong_package.response_plan.options == ["Basic", "Premium"]

print(
    "PASS 2 - exact cross-domain value Wedding is rejected before Gemini and cannot advance"
)


# ------------------------------------------------------------------
# 3. Correct package selection still progresses normally.
# ------------------------------------------------------------------

correct = orchestrator.handle_text(
    context=context,
    message_text="Basic",
)

assert context.quote.package == "Basic"
assert context.state == FlowState.QUOTE_COVERAGE
assert correct.response_plan.next_field == "coverage_type"

print(
    "PASS 3 - valid Basic selection still progresses to coverage"
)


# ------------------------------------------------------------------
# 4. Defense in depth: even if Gemini proposes an invented enum value from
#    a non-cross-domain phrase, Python rejects the proposed value.
# ------------------------------------------------------------------

bad_interpreter = QueueInterpreter(
    [
        meaning(
            SemanticAction.FIELD_VALUE,
            field_name="package",
            value="Wedding",
        )
    ]
)

orchestrator2 = ConversationOrchestrator(
    semantic_interpreter=bad_interpreter,
    supported_services=catalogue["supported_services"],
    packages_by_service=catalogue["packages_by_service"],
)

context2 = ConversationContext(
    state=FlowState.QUOTE_PACKAGE
)
context2.quote.service = "Wedding"

bad = orchestrator2.handle_text(
    context=context2,
    message_text="I choose the first thing",
)

assert bad.event.type.value == "INVALID_FIELD_VALUE"
assert context2.state == FlowState.QUOTE_PACKAGE
assert context2.quote.package is None

print(
    "PASS 4 - Python rejects an invalid Gemini-proposed package value"
)


# ------------------------------------------------------------------
# 5. Selected-package comparison also uses deterministic approved data before
#    asking keep/switch.
# ------------------------------------------------------------------

reconsider_interpreter = QueueInterpreter(
    [
        meaning(
            SemanticAction.PACKAGE_RECONSIDERATION,
            question_type=None,
            question_text="What's the difference between basic and premium",
        )
    ]
)

orchestrator3 = ConversationOrchestrator(
    semantic_interpreter=reconsider_interpreter,
    supported_services=catalogue["supported_services"],
    packages_by_service=catalogue["packages_by_service"],
)

coordinator3 = BusinessQuestionCoordinatorV3(
    orchestrator=orchestrator3,
    answer_service=answer_service,
    quote_adapter=None,
)

context3 = ConversationContext(
    state=FlowState.QUOTE_COVERAGE
)
context3.quote.service = "Wedding"
context3.quote.package = "Basic"

reconsider = orchestrator3.handle_text(
    context=context3,
    message_text="What's the difference between basic and premium",
)

assert context3.state == FlowState.PACKAGE_RECONFIRMATION

resolution3 = coordinator3.resolve_package_reconsideration(
    context=context3,
    question_text=reconsider.response_plan.business_question_text or "",
    question_type=reconsider.response_plan.business_question_type,
    customer_language="English",
)

assert "£950" in (resolution3.answer.answer_text or "")
assert "£1,200" in (resolution3.answer.answer_text or "")
assert context3.quote.package == "Basic"
assert resolution3.resume_plan.current_package == "Basic"
assert resolution3.resume_plan.options == ["Basic", "Premium"]

print(
    "PASS 5 - selected-package comparison answers exact data before keep/switch"
)


print()
print("=" * 72)
print("V3 PRODUCTION HOTFIX 1 REGRESSION PASSED")
print("=" * 72)
