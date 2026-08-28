from types import SimpleNamespace

from business_answer_service_v3 import (
    BusinessAnswerServiceV3,
)
from business_knowledge_adapter_v3 import (
    BusinessKnowledgeAdapterV3,
)
from business_question_coordinator_v3 import (
    BusinessQuestionCoordinatorV3,
)
from conversation_events import (
    ConversationEvent,
    EventType,
)
from conversation_models import (
    ConversationContext,
    FlowState,
)
from conversation_orchestrator import (
    ConversationOrchestrator,
)
from quote_adapter_v3 import (
    QuoteAdapterV3,
)
from semantic_contract import (
    SemanticAction,
    SemanticInterpretation,
)


class FakeKnowledgeModule:
    @staticmethod
    def get_business_knowledge(
        force_refresh=False,
    ):
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
                    "active": True,
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
                    "active": True,
                },
            ],
            "packages": [
                {
                    "service": "Wedding",
                    "package": "Basic",
                    "description": "Core coverage.",
                    "active": True,
                },
                {
                    "service": "Wedding",
                    "package": "Premium",
                    "description": "Extended coverage.",
                    "active": True,
                },
            ],
            "business_info": [
                {
                    "key": "office_hours",
                    "value": "9-5",
                    "active": True,
                }
            ],
            "faqs": [
                {
                    "question": "Drone?",
                    "answer": "Team confirmation required.",
                    "active": True,
                }
            ],
        }


class FakeQuoteModule:
    @staticmethod
    def calculate_quote(
        session,
    ):
        pricing = {
            "Basic": {
                "included": 4,
                "base": 950,
                "extra": 80,
            },
            "Premium": {
                "included": 6,
                "base": 1200,
                "extra": 100,
            },
        }[
            session["package"]
        ]

        duration = float(
            session["duration_hours"]
        )

        extra_hours = max(
            0,
            duration
            - pricing["included"],
        )

        total = (
            pricing["base"]
            + (
                extra_hours
                * pricing["extra"]
            )
        )

        return {
            "service":
                session["service"],
            "package":
                session["package"],
            "coverage_type":
                session["coverage_type"],
            "included_hours":
                pricing["included"],
            "duration_hours":
                duration,
            "base_price":
                pricing["base"],
            "extra_hours":
                extra_hours,
            "extra_hour_rate":
                pricing["extra"],
            "extra_hours_cost":
                extra_hours
                * pricing["extra"],
            "travel_fee":
                0,
            "quote_total":
                total,
            "status":
                "QUOTE_READY",
            "human_handoff":
                False,
        }


class FakeModels:
    def generate_content(
        self,
        **kwargs,
    ):
        return SimpleNamespace(
            parsed={
                "answer_found":
                    True,
                "answer_text":
                    (
                        "Basic has a lower starting price. "
                        "Premium includes more coverage time."
                    ),
                "should_offer_human":
                    False,
                "language":
                    "English",
            },
            text=None,
        )


class FakeGeminiClient:
    models = FakeModels()


class DummyInterpreter:
    def interpret(
        self,
        context,
        message_text,
        **kwargs,
    ):
        return SemanticInterpretation(
            action=
                SemanticAction
                .BUSINESS_QUESTION,
            question_type=
                "PACKAGE_COMPARISON",
            question_text=
                message_text,
            confidence=
                0.99,
            language=
                "English",
        )


knowledge = BusinessKnowledgeAdapterV3(
    service_module=
        FakeKnowledgeModule
)

catalogue = knowledge.get_catalogue()

assert catalogue["supported_services"] == [
    "Wedding"
]
assert catalogue["packages_by_service"]["Wedding"] == [
    "Basic",
    "Premium",
]

print("PASS 1 - V3 reads business catalogue through read-only adapter")


quote_adapter = QuoteAdapterV3(
    quote_module=
        FakeQuoteModule
)

context = ConversationContext(
    state=FlowState.QUOTE_READY
)

context.quote.service = "Wedding"
context.quote.package = "Premium"
context.quote.coverage_type = "Both"
context.quote.travel_required = "No"
context.quote.duration_hours = 8
context.quote.event_date = "12 October"
context.quote.location = "Birmingham"

quote = quote_adapter.calculate(
    context
)

assert quote["quote_total"] == 1400
assert context.quote_version == 1
assert context.quote_is_stale is False

print("PASS 2 - deterministic quote adapter produces £1400 example")


answer_service = BusinessAnswerServiceV3(
    knowledge_adapter=
        knowledge,
    client=
        FakeGeminiClient(),
)

before_quote = context.quote.as_dict()

answer = answer_service.answer(
    context=context,
    question_text=
        "Basic vs Premium?",
    question_type=
        "PACKAGE_COMPARISON",
)

assert answer.answer_found is True
assert context.quote.as_dict() == before_quote

print("PASS 3 - grounded answer service cannot mutate quote context")


orchestrator = ConversationOrchestrator(
    semantic_interpreter=
        DummyInterpreter(),
    supported_services=
        catalogue["supported_services"],
    packages_by_service=
        catalogue["packages_by_service"],
)

context = ConversationContext(
    state=FlowState.QUOTE_DURATION
)

context.quote.service = "Wedding"
context.quote.package = "Basic"
context.quote.coverage_type = "Both"
context.quote.travel_required = "No"

result = orchestrator.handle_text(
    context=context,
    message_text="Basic vs Premium?",
)

assert context.state == FlowState.BUSINESS_INTERRUPT

coordinator = BusinessQuestionCoordinatorV3(
    orchestrator=
        orchestrator,
    answer_service=
        answer_service,
    quote_adapter=
        quote_adapter,
)

resolution = coordinator.resolve(
    context=context,
    question_text=
        result.response_plan
        .business_question_text,
    question_type=
        result.response_plan
        .business_question_type,
)

assert context.state == FlowState.QUOTE_DURATION
assert resolution.resume_plan.next_field == "duration_hours"

print("PASS 4 - grounded business answer resumes exact interrupted field")

print()
print("=" * 72)
print("V3 BLOCK 6 OFFLINE BUSINESS INTEGRATION TEST PASSED")
print("=" * 72)
