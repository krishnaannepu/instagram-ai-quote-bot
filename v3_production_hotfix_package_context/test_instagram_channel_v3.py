from types import SimpleNamespace

from business_answer_service_v3 import BusinessAnswerServiceV3
from business_knowledge_adapter_v3 import BusinessKnowledgeAdapterV3
from business_question_coordinator_v3 import BusinessQuestionCoordinatorV3
from conversation_models import FlowState
from conversation_orchestrator import ConversationOrchestrator
from instagram_channel_adapter_v3 import InstagramChannelAdapterV3
from local_conversation_runtime_v3 import LocalConversationRuntimeV3
from quote_adapter_v3 import QuoteAdapterV3
from semantic_contract import SemanticAction, SemanticInterpretation
from session_repository_v3 import InMemorySessionRepositoryV3


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
                },
                {
                    "service": "Wedding",
                    "package": "Premium",
                },
            ],
            "business_info": [],
            "faqs": [],
        }


class FakeQuote:
    @staticmethod
    def calculate_quote(session):
        values = {
            "Basic": (4, 950, 80),
            "Premium": (6, 1200, 100),
        }[session["package"]]

        included, base, rate = values
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
                    "Basic Both starts at £950 and includes up to 4 hours. "
                    "Premium Both starts at £1,200 and includes up to 6 hours."
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


class CapturingSender:
    def __init__(self):
        self.sent = []

    def send_rendered(
        self,
        *,
        recipient_id,
        message,
    ):
        self.sent.append(
            (
                recipient_id,
                message,
            )
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
            question_text="price difference?",
        ),
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

sessions = InMemorySessionRepositoryV3()
sender = CapturingSender()

channel = InstagramChannelAdapterV3(
    runtime=runtime,
    session_repository=sessions,
    sender=sender,
)

sender_id = "customer-123"


def webhook_text(text, mid):
    return {
        "entry": [
            {
                "messaging": [
                    {
                        "sender": {
                            "id": sender_id
                        },
                        "message": {
                            "mid": mid,
                            "text": text,
                        },
                    }
                ]
            }
        ]
    }


def webhook_button(payload, mid):
    return {
        "entry": [
            {
                "messaging": [
                    {
                        "sender": {
                            "id": sender_id
                        },
                        "message": {
                            "mid": mid,
                            "text": "button",
                            "quick_reply": {
                                "payload": payload,
                            },
                        },
                    }
                ]
            }
        ]
    }


channel.process_webhook(
    webhook_button(
        "GET_QUOTE",
        "m1",
    )
)

context = sessions.get(sender_id)

assert context.state == FlowState.QUOTE_SERVICE
assert sender.sent[-1][1].buttons[0].label == "Wedding"

print(
    "PASS 1 - Meta quick reply enters V3 runtime through channel adapter"
)


channel.process_webhook(
    webhook_text("Wedding", "m2")
)
channel.process_webhook(
    webhook_text("Basic", "m3")
)

assert context.quote.package == "Basic"
assert context.state == FlowState.QUOTE_COVERAGE

print(
    "PASS 2 - text messages share the same persistent sender session"
)


before_count = len(sender.sent)

channel.process_webhook(
    webhook_text(
        "price difference?",
        "m4",
    )
)

new_messages = sender.sent[before_count:]

assert context.state == FlowState.PACKAGE_RECONFIRMATION
assert len(new_messages) == 2
assert "£950" in new_messages[0][1].text
assert "Basic selected" in new_messages[1][1].text

button_payloads = [
    button.payload
    for button in new_messages[1][1].buttons
]

assert "KEEP_CURRENT_PACKAGE" in button_payloads
assert "SWITCH_PACKAGE_PREMIUM" in button_payloads

print(
    "PASS 3 - package comparison sends answer then keep/switch buttons"
)


# Use real quick-reply payload path for switching.
channel.process_webhook(
    webhook_button(
        "SWITCH_PACKAGE_PREMIUM",
        "m5",
    )
)

assert context.quote.package == "Premium"
assert context.state == FlowState.QUOTE_COVERAGE

print(
    "PASS 4 - Switch to Premium button normalizes to same V3 package event"
)


# Remaining customer replies.
for index, text in enumerate(
    [
        "both",
        "no",
        "8 hours",
        "12 October",
        "Birmingham",
    ],
    start=6,
):
    channel.process_webhook(
        webhook_text(
            text,
            f"m{index}",
        )
    )

assert context.state == FlowState.QUOTE_READY
assert "Total: £1400" in sender.sent[-1][1].text

print(
    "PASS 5 - webhook path reaches deterministic £1400 quote"
)


# Echoes are ignored.
echo_payload = {
    "entry": [
        {
            "messaging": [
                {
                    "sender": {
                        "id": sender_id
                    },
                    "message": {
                        "mid": "echo1",
                        "text": "echo",
                        "is_echo": True,
                    },
                }
            ]
        }
    ]
}

before = len(sender.sent)

result = channel.process_webhook(
    echo_payload
)

assert len(sender.sent) == before
assert result.processed_messages == 0

print(
    "PASS 6 - Instagram echo messages are ignored"
)

print()
print("=" * 72)
print("V3 BLOCK 8 INSTAGRAM CHANNEL ADAPTER TEST PASSED")
print("=" * 72)
