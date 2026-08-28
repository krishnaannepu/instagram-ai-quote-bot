from types import SimpleNamespace

from business_answer_service_v3 import BusinessAnswerServiceV3
from business_knowledge_adapter_v3 import BusinessKnowledgeAdapterV3
from business_question_coordinator_v3 import BusinessQuestionCoordinatorV3
from conversation_models import ConversationContext, FlowState
from conversation_orchestrator import ConversationOrchestrator
from email_delivery_adapter_v3 import EmailDeliveryAdapterV3
from lead_persistence_adapter_v3 import LeadPersistenceAdapterV3
from local_conversation_runtime_v3 import LocalConversationRuntimeV3
from quote_adapter_v3 import QuoteAdapterV3
from quote_completion_service_v3 import QuoteCompletionServiceV3
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
                    "description": "Core coverage.",
                },
                {
                    "service": "Wedding",
                    "package": "Premium",
                    "description": "Extended coverage.",
                },
            ],
            "business_info": [],
            "faqs": [
                {
                    "question": "Discounts?",
                    "answer": "Discount information requires confirmed policy.",
                }
            ],
        }


class FakeQuote:
    @staticmethod
    def calculate_quote(session):
        included, base, rate = {
            "Basic": (4, 950, 80),
            "Premium": (6, 1200, 100),
        }[
            session["package"]
        ]

        hours = float(
            session["duration_hours"]
        )

        extra = max(
            0,
            hours - included,
        )

        return {
            "service":
                session["service"],
            "package":
                session["package"],
            "coverage_type":
                session["coverage_type"],
            "duration_hours":
                hours,
            "included_hours":
                included,
            "base_price":
                base,
            "extra_hours":
                extra,
            "extra_hour_rate":
                rate,
            "extra_hours_cost":
                extra * rate,
            "travel_fee":
                0,
            "quote_total":
                base + extra * rate,
            "status":
                "QUOTE_READY",
            "human_handoff":
                False,
        }


class FakeSheets:
    leads = {}
    next_id = 1

    @classmethod
    def save_completed_lead(
        cls,
        session,
        quote_data=None,
        ig_handle="",
    ):
        lead_id = (
            session.get(
                "active_lead_id"
            )
            or f"LEAD-{cls.next_id:04d}"
        )

        if lead_id not in cls.leads:
            cls.next_id += 1

        lead = {
            "lead_id":
                lead_id,
            "sender_id":
                session.get(
                    "sender_id",
                    "",
                ),
            "service":
                session.get(
                    "service",
                    "",
                ),
            "package":
                session.get(
                    "package",
                    "",
                ),
            "coverage_type":
                session.get(
                    "coverage_type",
                    "",
                ),
            "event_date":
                session.get(
                    "event_date",
                    "",
                ),
            "location":
                session.get(
                    "location",
                    "",
                ),
            "duration_hours":
                session.get(
                    "duration_hours",
                    "",
                ),
            "travel_required":
                session.get(
                    "travel_required",
                    "",
                ),
            "base_price":
                (quote_data or {}).get(
                    "base_price",
                    "",
                ),
            "extra_hours":
                (quote_data or {}).get(
                    "extra_hours",
                    "",
                ),
            "extra_hour_rate":
                (quote_data or {}).get(
                    "extra_hour_rate",
                    "",
                ),
            "travel_fee":
                (quote_data or {}).get(
                    "travel_fee",
                    "",
                ),
            "quote_total":
                (quote_data or {}).get(
                    "quote_total",
                    "",
                ),
            "status":
                (quote_data or {}).get(
                    "status",
                    "QUOTE_READY",
                ),
            "human_handoff":
                (quote_data or {}).get(
                    "human_handoff",
                    False,
                ),
        }

        cls.leads[
            lead_id
        ] = lead

        session[
            "active_lead_id"
        ] = lead_id

        return dict(
            lead
        )

    @classmethod
    def update_lead(
        cls,
        lead_id,
        updates,
    ):
        current = dict(
            cls.leads.get(
                lead_id,
                {
                    "lead_id":
                        lead_id,
                },
            )
        )

        current.update(
            updates
        )

        cls.leads[
            lead_id
        ] = current

        return dict(
            current
        )


class FakeEmail:
    sent = []
    owner_notifications = []

    @classmethod
    def send_email(
        cls,
        recipient,
        subject,
        body,
    ):
        cls.sent.append(
            {
                "recipient":
                    recipient,
                "subject":
                    subject,
                "body":
                    body,
            }
        )

        return {
            "id":
                "fake-email-1"
        }

    @classmethod
    def send_new_lead_email(
        cls,
        session,
        quote,
        lead,
    ):
        cls.owner_notifications.append(
            {
                "session":
                    dict(
                        session
                    ),
                "quote":
                    dict(
                        quote
                    ),
                "lead":
                    dict(
                        lead
                    ),
            }
        )

        return {
            "id":
                "owner-email-1"
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
                        "Basic Both starts at £950 and Premium Both "
                        "starts at £1,200."
                    ),
                "should_offer_human":
                    False,
                "language":
                    "English",
            },
            text=None,
        )


class FakeClient:
    models = FakeModels()


class QueueInterpreter:
    def __init__(
        self,
        meanings,
    ):
        self.meanings = list(
            meanings
        )

    def interpret(
        self,
        context,
        message_text,
        **kwargs,
    ):
        if not self.meanings:
            raise AssertionError(
                f"No semantic meaning scripted for: {message_text}"
            )

        return self.meanings.pop(
            0
        )


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
        m(
            SemanticAction.FIELD_VALUE,
            "service",
            "Wedding",
        ),
        m(
            SemanticAction.FIELD_VALUE,
            "package",
            "Premium",
        ),
        m(
            SemanticAction.FIELD_VALUE,
            "coverage_type",
            "Both",
        ),
        m(
            SemanticAction.FIELD_VALUE,
            "travel_required",
            "No",
        ),
        m(
            SemanticAction.FIELD_VALUE,
            "duration_hours",
            8,
        ),
        m(
            SemanticAction.FIELD_VALUE,
            "event_date",
            "12 October",
        ),
        m(
            SemanticAction.FIELD_VALUE,
            "location",
            "Birmingham",
        ),

        # Side question while email Yes/No is pending.
        m(
            SemanticAction.BUSINESS_QUESTION,
            question_type="DISCOUNT",
            question_text="Any discounts?",
        ),

        # Typed yes after the side question.
        m(
            SemanticAction.EMAIL_YES,
        ),
    ]
)

orchestrator = ConversationOrchestrator(
    semantic_interpreter=interpreter,
    supported_services=catalogue[
        "supported_services"
    ],
    packages_by_service=catalogue[
        "packages_by_service"
    ],
)

quote_adapter = QuoteAdapterV3(
    quote_module=FakeQuote
)

lead_persistence = LeadPersistenceAdapterV3(
    sheets_module=FakeSheets
)

email_delivery = EmailDeliveryAdapterV3(
    email_module=FakeEmail,
    lead_persistence=
        lead_persistence,
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

quote_completion = QuoteCompletionServiceV3(
    orchestrator=orchestrator,
    quote_adapter=quote_adapter,
    lead_persistence=lead_persistence,
    email_delivery=email_delivery,
)

runtime = LocalConversationRuntimeV3(
    orchestrator=orchestrator,
    business_coordinator=coordinator,
    quote_completion=quote_completion,
    email_delivery=email_delivery,
)

context = ConversationContext()
context.metadata[
    "sender_id"
] = "customer-123"


runtime.handle_button(
    context=context,
    payload="GET_QUOTE",
)

for text in [
    "Wedding",
    "Premium",
    "Both",
    "No",
    "8 hours",
    "12 October",
]:
    runtime.handle_text(
        context=context,
        message_text=text,
    )

quote_turn = runtime.handle_text(
    context=context,
    message_text="Birmingham",
)

assert context.state == FlowState.EMAIL_CONFIRMATION
assert quote_turn.quote[
    "quote_total"
] == 1400
assert len(
    quote_turn.messages
) == 2
assert "Total: £1400" in quote_turn.messages[0].text
assert "copy of your quote" in quote_turn.messages[1].text
assert context.lifecycle.quote_persisted is True
assert context.lifecycle.active_lead_id
assert len(
    FakeEmail.owner_notifications
) == 1

print(
    "PASS 1 - quote completion persists lead and enters EMAIL_CONFIRMATION"
)


side_question = runtime.handle_text(
    context=context,
    message_text="Any discounts?",
)

assert context.state == FlowState.EMAIL_CONFIRMATION
assert len(
    side_question.messages
) == 2
assert "£950" in side_question.messages[0].text
assert "copy of your quote" in side_question.messages[1].text

print(
    "PASS 2 - side business question does not erase email Yes/No decision"
)


yes_turn = runtime.handle_text(
    context=context,
    message_text="yes please",
)

assert context.state == FlowState.EMAIL_ADDRESS
assert "email address" in yes_turn.messages[0].text

print(
    "PASS 3 - typed email acceptance moves to EMAIL_ADDRESS"
)


invalid = runtime.handle_text(
    context=context,
    message_text="krishna@invalid",
)

assert context.state == FlowState.EMAIL_ADDRESS
assert "does not look valid" in invalid.messages[0].text

print(
    "PASS 4 - malformed email is rejected deterministically"
)


email_turn = runtime.handle_text(
    context=context,
    message_text="customer@example.com",
)

assert context.state == FlowState.POST_QUOTE
assert context.customer.email == "customer@example.com"
assert context.lifecycle.quote_email_sent is True
assert len(
    email_turn.messages
) == 2
assert "sent to your email" in email_turn.messages[0].text
assert "What would you like to do next?" in email_turn.messages[1].text

customer_mail = FakeEmail.sent[-1]

assert customer_mail[
    "recipient"
] == "customer@example.com"

assert "smileshoots" not in (
    customer_mail[
        "subject"
    ]
    + customer_mail[
        "body"
    ]
).lower()

assert "testing" not in (
    customer_mail[
        "subject"
    ]
    + customer_mail[
        "body"
    ]
).lower()

assert "£1,400.00" in customer_mail[
    "body"
]

print(
    "PASS 5 - customer quote email is sent with V3-safe copy"
)


post_buttons = [
    button.label
    for button in email_turn.messages[1].buttons
]

assert post_buttons == [
    "Speak to Team",
    "Start New Quote",
    "Finish",
]

print(
    "PASS 6 - post-quote menu preserves the three required actions"
)


# Email No button path.
context2 = ConversationContext(
    state=FlowState.EMAIL_CONFIRMATION
)

context2.lifecycle.quote_data = {
    "quote_total":
        100,
}

no_turn = runtime.handle_button(
    context=context2,
    payload="EMAIL_NO",
)

assert context2.state == FlowState.POST_QUOTE
assert "What would you like to do next?" in no_turn.messages[0].text

print(
    "PASS 7 - EMAIL_NO goes directly to post-quote options"
)

print()
print("=" * 72)
print("V3 BLOCK 9 POST-QUOTE + EMAIL TEST PASSED")
print("=" * 72)
