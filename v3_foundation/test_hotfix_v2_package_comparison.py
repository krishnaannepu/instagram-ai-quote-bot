
from types import SimpleNamespace

from business_answer_service_v3 import BusinessAnswerServiceV3
from business_knowledge_adapter_v3 import BusinessKnowledgeAdapterV3
from business_question_coordinator_v3 import BusinessQuestionCoordinatorV3
from conversation_models import ConversationContext, FlowState
from conversation_orchestrator import ConversationOrchestrator
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
                {"service": "Wedding", "package": "Basic"},
                {"service": "Wedding", "package": "Premium"},
                {"service": "Birthday", "package": "Basic"},
                {"service": "Birthday", "package": "Premium"},
            ],
            "business_info": [],
            "faqs": [],
        }


class NeverCallModels:
    def generate_content(self, **kwargs):
        raise AssertionError(
            "Gemini business-answer generation must not be needed "
            "for deterministic package comparison."
        )


class FakeClient:
    models = NeverCallModels()


class ComparisonInterpreter:
    def interpret(self, context, message_text, **kwargs):
        return SemanticInterpretation(
            action=SemanticAction.BUSINESS_QUESTION,
            question_type=None,
            question_text=message_text,
            confidence=0.99,
            language="English",
        )


knowledge = BusinessKnowledgeAdapterV3(
    service_module=FakeKnowledge
)
catalogue = knowledge.get_catalogue()

orch = ConversationOrchestrator(
    semantic_interpreter=ComparisonInterpreter(),
    supported_services=catalogue["supported_services"],
    packages_by_service=catalogue["packages_by_service"],
)

answer_service = BusinessAnswerServiceV3(
    knowledge_adapter=knowledge,
    client=FakeClient(),
)

coordinator = BusinessQuestionCoordinatorV3(
    orchestrator=orch,
    answer_service=answer_service,
    quote_adapter=None,
)

context = ConversationContext(state=FlowState.QUOTE_PACKAGE)
context.quote.service = "Wedding"

result = orch.handle_text(
    context=context,
    message_text="What's the difference between basic and premium",
)

assert context.state == FlowState.BUSINESS_INTERRUPT

resolution = coordinator.resolve(
    context=context,
    question_text=result.response_plan.business_question_text,
    question_type=result.response_plan.business_question_type,
    customer_language="English",
)

text = resolution.answer.answer_text
assert "For Wedding" in text
assert "Photography: £500" in text
assert "Both: £950" in text
assert "Photography: £700" in text
assert "Both: £1,200" in text
assert "which service" not in text.lower()
assert "Birthday" not in text
assert context.state == FlowState.QUOTE_PACKAGE
assert resolution.resume_plan.next_field == "package"

print("PASS 1 - selected Wedding service drives exact Basic/Premium comparison")
print("PASS 2 - answer uses approved Wedding prices only")
print("PASS 3 - comparison cannot ask for service again")
print("PASS 4 - flow resumes package selection after answer")

print()
print("=" * 72)
print("V3 PRODUCTION HOTFIX V2 PACKAGE COMPARISON TEST PASSED")
print("=" * 72)
