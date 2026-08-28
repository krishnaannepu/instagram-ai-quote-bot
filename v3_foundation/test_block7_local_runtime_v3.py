from types import SimpleNamespace

from business_answer_service_v3 import BusinessAnswerServiceV3
from business_knowledge_adapter_v3 import BusinessKnowledgeAdapterV3
from business_question_coordinator_v3 import BusinessQuestionCoordinatorV3
from conversation_models import ConversationContext, FlowState
from conversation_orchestrator import ConversationOrchestrator
from customer_response_renderer_v3 import CustomerResponseRendererV3
from local_conversation_runtime_v3 import LocalConversationRuntimeV3
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
                    "description": "Core coverage.",
                },
                {
                    "service": "Wedding",
                    "package": "Premium",
                    "description": "Extended coverage.",
                },
            ],
            "business_info": [],
            "faqs": [],
        }


class FakeQuote:
    @staticmethod
    def calculate_quote(session):
        row = {
            "Basic": (4, 950, 80),
            "Premium": (6, 1200, 100),
        }[session["package"]]

        included, base, rate = row
        hours = float(session["duration_hours"])
        extra = max(0, hours - included)

        return {
            "service": session["service"],
            "package": session["package"],
            "coverage_type": session["coverage_type"],
            "duration_hours": hours,
            "base_price": base,
            "included_hours": included,
            "extra_hours": extra,
            "extra_hour_rate": rate,
            "extra_hours_cost": extra * rate,
            "travel_fee": 0,
            "quote_total": base + extra * rate,
        }


class FakeModels:
    def generate_content(self, **kwargs):
        return SimpleNamespace(
            parsed={
                "answer_found": True,
                "answer_text": (
                    "Basic includes up to 4 hours and Both starts at £950. "
                    "Premium includes up to 6 hours and Both starts at £1,200."
                ),
                "should_offer_human": False,
                "language": "English",
            },
            text=None,
        )


class FakeClient:
    models = FakeModels()


class QueueInterpreter:
    def __init__(self, values):
        self.values = list(values)

    def interpret(self, context, message_text, **kwargs):
        return self.values.pop(0)


def m(
    action,
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
        m(SemanticAction.FIELD_VALUE, "service", "Wedding"),
        m(SemanticAction.FIELD_VALUE, "package", "Basic"),
        m(
            SemanticAction.PACKAGE_RECONSIDERATION,
            question_type="PACKAGE_COMPARISON_WITH_PRICING",
            question_text="tell me price difference one more time",
        ),
        m(SemanticAction.PAUSE),
        m(SemanticAction.SWITCH_PACKAGE, value="Premium"),
        m(SemanticAction.FIELD_VALUE, "coverage_type", "Both"),
        m(SemanticAction.FIELD_VALUE, "travel_required", "No"),
        m(SemanticAction.FIELD_VALUE, "duration_hours", 8),
        m(SemanticAction.FIELD_VALUE, "event_date", "12 October"),
        m(SemanticAction.FIELD_VALUE, "location", "Birmingham"),
    ]
)

orchestrator = ConversationOrchestrator(
    semantic_interpreter=interpreter,
    supported_services=catalogue["supported_services"],
    packages_by_service=catalogue["packages_by_service"],
)

quote_adapter = QuoteAdapterV3(
    quote_module=FakeQuote
)

answer_service = BusinessAnswerServiceV3(
    knowledge_adapter=knowledge,
    client=FakeClient(),
)

coordinator = BusinessQuestionCoordinatorV3(
    orchestrator=orchestrator,
    answer_service=answer_service,
    quote_adapter=quote_adapter,
)

runtime = LocalConversationRuntimeV3(
    orchestrator=orchestrator,
    business_coordinator=coordinator,
    quote_adapter=quote_adapter,
)

context = ConversationContext()

runtime.handle_button(
    context=context,
    payload="GET_QUOTE",
)
runtime.handle_text(
    context=context,
    message_text="Wedding",
)
runtime.handle_text(
    context=context,
    message_text="Basic",
)

comparison = runtime.handle_text(
    context=context,
    message_text="wait tell me price difference one more time",
)

assert context.state == FlowState.PACKAGE_RECONFIRMATION
assert len(comparison.messages) == 2
assert "£950" in comparison.messages[0].text
assert "£1,200" in comparison.messages[0].text
assert "Basic selected" in comparison.messages[1].text
assert "continue with Basic" in comparison.messages[1].text
assert "switch" in comparison.messages[1].text.lower()

print(
    "PASS 1 - comparison is answered before keep/switch reconfirmation"
)

paused = runtime.handle_text(
    context=context,
    message_text="okay",
)

assert context.state == FlowState.PACKAGE_RECONFIRMATION
assert "Basic selected" in paused.messages[0].text

print(
    "PASS 2 - bare okay remains at package reconfirmation"
)

switched = runtime.handle_text(
    context=context,
    message_text="Premium kardo",
)

assert context.quote.package == "Premium"
assert context.state == FlowState.QUOTE_COVERAGE
assert "Photography" in switched.messages[0].text
assert "Videography" in switched.messages[0].text

print(
    "PASS 3 - switching package resumes exact interrupted coverage field"
)

for text in [
    "both",
    "no",
    "8 hours",
    "12 October",
]:
    runtime.handle_text(
        context=context,
        message_text=text,
    )

final_result = runtime.handle_text(
    context=context,
    message_text="Birmingham",
)

assert context.state == FlowState.QUOTE_READY
assert final_result.quote["quote_total"] == 1400
assert "Total: £1400" in final_result.messages[0].text

print(
    "PASS 4 - full local runtime produces deterministic £1400 quote"
)

for message in comparison.messages + [final_result.messages[0]]:
    lower = message.text.lower()
    assert "smileshoots" not in lower
    assert "testing" not in lower

print(
    "PASS 5 - customer-facing output respects naming/copy constraints"
)

print()
print("=" * 72)
print("V3 BLOCK 7 OFFLINE LOCAL RUNTIME TEST PASSED")
print("=" * 72)
