from types import SimpleNamespace

from business_answer_service_v3 import BusinessAnswerServiceV3
from business_knowledge_adapter_v3 import BusinessKnowledgeAdapterV3
from conversation_models import ConversationContext, FlowState
from conversation_orchestrator import ConversationOrchestrator
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
                {"service": "Wedding", "package": "Basic"},
                {"service": "Wedding", "package": "Premium"},
            ],
            "business_info": [],
            "faqs": [],
        }


class OneShotInterpreter:
    def __init__(self, interpretation):
        self.interpretation = interpretation

    def interpret(self, context, message_text, **kwargs):
        return self.interpretation


# ------------------------------------------------------------------
# DEFECT 1 from production screenshot:
# State expects package, Gemini incorrectly returns package="Wedding".
# Python must reject it and remain QUOTE_PACKAGE.
# ------------------------------------------------------------------

context = ConversationContext(
    state=FlowState.QUOTE_PACKAGE
)
context.quote.service = "Wedding"

orchestrator = ConversationOrchestrator(
    semantic_interpreter=OneShotInterpreter(
        SemanticInterpretation(
            action=SemanticAction.FIELD_VALUE,
            field_name="package",
            value="Wedding",
            confidence=0.90,
            language="English",
        )
    ),
    supported_services=[
        "Wedding",
        "Birthday",
        "Portrait",
        "Event",
    ],
    packages_by_service={
        "Wedding": [
            "Basic",
            "Premium",
        ],
    },
)

result = orchestrator.handle_text(
    context=context,
    message_text="Wedding",
)

assert context.state == FlowState.QUOTE_PACKAGE
assert context.quote.package is None
assert result.event.type.value == "INVALID_FIELD_VALUE"
assert result.response_plan.next_field == "package"
assert result.response_plan.options == [
    "Basic",
    "Premium",
]

print(
    "PASS 1 - 'Wedding' cannot be accepted as a package or advance the state"
)


# ------------------------------------------------------------------
# DEFECT 2 from production screenshot:
# Wedding is already selected, customer asks Basic vs Premium.
# Answer must use Wedding rows and must not ask which service.
# ------------------------------------------------------------------

knowledge = BusinessKnowledgeAdapterV3(
    service_module=FakeKnowledge
)

class ExplodingModels:
    def generate_content(self, **kwargs):
        raise AssertionError(
            "Gemini must not be needed for the standard package comparison."
        )

class ExplodingClient:
    models = ExplodingModels()

answer_service = BusinessAnswerServiceV3(
    knowledge_adapter=knowledge,
    client=ExplodingClient(),
)

context = ConversationContext(
    state=FlowState.QUOTE_PACKAGE
)
context.quote.service = "Wedding"

answer = answer_service.answer(
    context=context,
    question_text=(
        "What's the difference between basic and premium"
    ),
    question_type=None,
    customer_language="English",
)

assert answer.answer_found is True
assert "Wedding" in answer.answer_text
assert "Basic" in answer.answer_text
assert "Premium" in answer.answer_text
assert "£500" in answer.answer_text
assert "£650" in answer.answer_text
assert "£950" in answer.answer_text
assert "£700" in answer.answer_text
assert "£850" in answer.answer_text
assert "£1,200" in answer.answer_text
assert "which service" not in answer.answer_text.lower()

print(
    "PASS 2 - package comparison uses selected Wedding service and exact approved prices"
)

print(
    "PASS 3 - standard Basic/Premium comparison no longer depends on Gemini wording"
)

print()
print("=" * 72)
print("V3 PRODUCTION DEFECT HOTFIX REGRESSION PASSED")
print("=" * 72)
