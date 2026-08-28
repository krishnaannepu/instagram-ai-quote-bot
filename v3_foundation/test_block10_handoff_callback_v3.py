from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from business_answer_service_v3 import BusinessAnswerServiceV3
from business_knowledge_adapter_v3 import BusinessKnowledgeAdapterV3
from business_question_coordinator_v3 import BusinessQuestionCoordinatorV3
from conversation_models import ConversationContext, FlowState
from conversation_orchestrator import ConversationOrchestrator
from email_delivery_adapter_v3 import EmailDeliveryAdapterV3
from handoff_callback_service_v3 import HandoffCallbackServiceV3
from lead_persistence_adapter_v3 import LeadPersistenceAdapterV3
from local_conversation_runtime_v3 import LocalConversationRuntimeV3
from quote_adapter_v3 import QuoteAdapterV3
from quote_completion_service_v3 import QuoteCompletionServiceV3
from semantic_contract import SemanticAction, SemanticInterpretation


class FakeKnowledge:
    @staticmethod
    def get_business_knowledge(force_refresh=False):
        return {
            "pricing": [
                {
                    "service": "Wedding",
                    "package": "Premium",
                    "included_hours": 6,
                    "photography_price": 700,
                    "videography_price": 850,
                    "both_price": 1200,
                    "extra_hour_rate": 100,
                    "travel_fee": 0,
                }
            ],
            "packages": [
                {
                    "service": "Wedding",
                    "package": "Premium",
                    "description": "Extended coverage.",
                }
            ],
            "business_info": [],
            "faqs": [],
        }


class FakeQuote:
    @staticmethod
    def calculate_quote(session):
        return {
            "service": session["service"],
            "package": session["package"],
            "coverage_type": session["coverage_type"],
            "duration_hours": float(session["duration_hours"]),
            "included_hours": 6,
            "base_price": 1200,
            "extra_hours": 2,
            "extra_hour_rate": 100,
            "extra_hours_cost": 200,
            "travel_fee": 0,
            "quote_total": 1400,
            "status": "QUOTE_READY",
            "human_handoff": False,
        }


class FakeSheets:
    leads = {}
    counter = 1

    @classmethod
    def save_completed_lead(
        cls,
        session,
        quote_data=None,
        ig_handle="",
    ):
        lead_id = (
            session.get("active_lead_id")
            or f"LEAD-{cls.counter:04d}"
        )

        if lead_id not in cls.leads:
            cls.counter += 1

        lead = {
            "lead_id": lead_id,
            "sender_id": session.get("sender_id", ""),
            "service": session.get("service", ""),
            "package": session.get("package", ""),
            "coverage_type": session.get("coverage_type", ""),
            "event_date": session.get("event_date", ""),
            "location": session.get("location", ""),
            "duration_hours": session.get("duration_hours", ""),
            "travel_required": session.get("travel_required", ""),
            "status": (quote_data or {}).get("status", "QUOTE_READY"),
            "human_handoff": (quote_data or {}).get(
                "human_handoff",
                False,
            ),
        }

        cls.leads[lead_id] = dict(lead)
        session["active_lead_id"] = lead_id

        return dict(lead)

    @classmethod
    def update_lead(
        cls,
        lead_id,
        updates,
    ):
        lead = dict(
            cls.leads.get(
                lead_id,
                {"lead_id": lead_id},
            )
        )
        lead.update(updates)
        cls.leads[lead_id] = lead
        return dict(lead)


class FakeEmail:
    handoffs = []
    callbacks = []
    customer_emails = []
    owner_leads = []

    @classmethod
    def send_email(
        cls,
        recipient,
        subject,
        body,
    ):
        cls.customer_emails.append(
            {
                "recipient": recipient,
                "subject": subject,
                "body": body,
            }
        )
        return {"id": "customer-email"}

    @classmethod
    def send_new_lead_email(
        cls,
        session,
        quote,
        lead,
    ):
        cls.owner_leads.append(
            (dict(session), dict(quote), dict(lead))
        )
        return {"id": "owner-lead"}

    @classmethod
    def send_handoff_notification(
        cls,
        session,
        lead,
        office_open,
        business_phone="",
    ):
        cls.handoffs.append(
            {
                "session": dict(session),
                "lead": dict(lead),
                "office_open": office_open,
                "business_phone": business_phone,
            }
        )
        return {"id": "handoff-email"}

    @classmethod
    def send_callback_request_email(
        cls,
        session,
        lead,
    ):
        cls.callbacks.append(
            {
                "session": dict(session),
                "lead": dict(lead),
            }
        )
        return {"id": "callback-email"}


class FakeModels:
    def generate_content(self, **kwargs):
        return SimpleNamespace(
            parsed={
                "answer_found": True,
                "answer_text": "Approved answer.",
                "should_offer_human": False,
                "language": "English",
            },
            text=None,
        )


class FakeClient:
    models = FakeModels()


class QueueInterpreter:
    def __init__(self, meanings=None):
        self.meanings = list(meanings or [])

    def interpret(self, context, message_text, **kwargs):
        if not self.meanings:
            raise AssertionError(
                f"No semantic result scripted for {message_text!r}"
            )
        return self.meanings.pop(0)


knowledge = BusinessKnowledgeAdapterV3(
    service_module=FakeKnowledge
)
catalogue = knowledge.get_catalogue()

orchestrator = ConversationOrchestrator(
    semantic_interpreter=QueueInterpreter(),
    supported_services=catalogue["supported_services"],
    packages_by_service=catalogue["packages_by_service"],
)

quote_adapter = QuoteAdapterV3(
    quote_module=FakeQuote
)

lead_persistence = LeadPersistenceAdapterV3(
    sheets_module=FakeSheets
)

email_delivery = EmailDeliveryAdapterV3(
    email_module=FakeEmail,
    lead_persistence=lead_persistence,
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

handoff_service = HandoffCallbackServiceV3(
    lead_persistence=lead_persistence,
    email_delivery=email_delivery,
    business_phone="020 7946 0123",
    now_provider=lambda: datetime(
        2026,
        8,
        27,
        14,
        0,
        tzinfo=ZoneInfo("Europe/London"),
    ),
)

runtime = LocalConversationRuntimeV3(
    orchestrator=orchestrator,
    business_coordinator=coordinator,
    quote_completion=quote_completion,
    email_delivery=email_delivery,
    handoff_service=handoff_service,
)

context = ConversationContext(
    state=FlowState.POST_QUOTE
)
context.metadata["sender_id"] = "customer-123"
context.quote.service = "Wedding"
context.quote.package = "Premium"
context.quote.coverage_type = "Both"
context.quote.travel_required = "No"
context.quote.duration_hours = 8
context.quote.event_date = "12 October"
context.quote.location = "Birmingham"
context.lifecycle.quote_data = {
    "service": "Wedding",
    "package": "Premium",
    "coverage_type": "Both",
    "duration_hours": 8,
    "base_price": 1200,
    "extra_hours": 2,
    "extra_hour_rate": 100,
    "extra_hours_cost": 200,
    "travel_fee": 0,
    "quote_total": 1400,
    "status": "QUOTE_READY",
    "human_handoff": False,
}


# ------------------------------------------------------------------
# 1. Speak to Team
# ------------------------------------------------------------------

handoff = runtime.handle_button(
    context=context,
    payload="SPEAK_TO_TEAM",
)

assert context.state == FlowState.HANDOFF_OPTIONS
assert context.lifecycle.handoff_requested is True
assert context.lifecycle.active_lead_id
assert len(FakeEmail.handoffs) == 1
assert "020 7946 0123" in handoff.messages[0].text

labels = [
    button.label
    for button in handoff.messages[0].buttons
]

assert labels == [
    "Request Callback",
    "Start New Quote",
    "Finish",
]

print("PASS 1 - Speak to Team creates handoff once and shows handoff options")


# ------------------------------------------------------------------
# 2. Repeated handoff does not duplicate notification
# ------------------------------------------------------------------

second_handoff = runtime.handle_button(
    context=context,
    payload="SPEAK_TO_TEAM",
)

assert context.state == FlowState.HANDOFF_OPTIONS
assert len(FakeEmail.handoffs) == 1
assert "already with our team" in second_handoff.messages[0].text

print("PASS 2 - repeated handoff does not send duplicate owner notification")


# ------------------------------------------------------------------
# 3. Request callback
# ------------------------------------------------------------------

callback_start = runtime.handle_button(
    context=context,
    payload="REQUEST_CALLBACK",
)

assert context.state == FlowState.CALLBACK_PHONE
assert "phone number" in callback_start.messages[0].text.lower()

print("PASS 3 - Request Callback moves to deterministic phone collection")


# ------------------------------------------------------------------
# 4. Invalid phone
# ------------------------------------------------------------------

invalid = runtime.handle_text(
    context=context,
    message_text="123",
)

assert context.state == FlowState.CALLBACK_PHONE
assert "does not look valid" in invalid.messages[0].text

print("PASS 4 - invalid callback phone is rejected without Gemini")


# ------------------------------------------------------------------
# 5. Valid phone
# ------------------------------------------------------------------

phone_turn = runtime.handle_text(
    context=context,
    message_text="+44 7700 900123",
)

assert context.state == FlowState.CALLBACK_PREFERENCE
assert context.customer.phone == "+44 7700 900123"

preference_labels = [
    button.label
    for button in phone_turn.messages[0].buttons
]

assert preference_labels == [
    "ASAP",
    "Morning",
    "Afternoon",
]

print("PASS 5 - valid phone moves to callback preference")


# ------------------------------------------------------------------
# 6. Preference button completes callback
# ------------------------------------------------------------------

callback_done = runtime.handle_button(
    context=context,
    payload="CALLBACK_ASAP",
)

assert context.state == FlowState.CALLBACK_RECORDED
assert context.customer.callback_preference == "ASAP"
assert context.lifecycle.callback_request_sent is True
assert len(FakeEmail.callbacks) == 1

done_labels = [
    button.label
    for button in callback_done.messages[0].buttons
]

assert done_labels == [
    "Start New Quote",
    "Finish",
]

lead = FakeSheets.leads[
    context.lifecycle.active_lead_id
]

assert lead["customer_phone"] == "+44 7700 900123"
assert lead["callback_preference"] == "ASAP"
assert lead["handoff_status"] == "CALLBACK_REQUESTED"
assert lead["status"] == "CALLBACK_REQUESTED"

print("PASS 6 - callback preference records lead and sends one priority email")


# ------------------------------------------------------------------
# 7. Duplicate callback request
# ------------------------------------------------------------------

duplicate = runtime.handle_button(
    context=context,
    payload="REQUEST_CALLBACK",
)

assert context.state == FlowState.CALLBACK_RECORDED
assert len(FakeEmail.callbacks) == 1
assert "already recorded" in duplicate.messages[0].text.lower()

print("PASS 7 - duplicate callback request is blocked")


# ------------------------------------------------------------------
# 8. Start New Quote clears human-contact lifecycle
# ------------------------------------------------------------------

new_quote = runtime.handle_button(
    context=context,
    payload="START_NEW_QUOTE",
)

assert context.state == FlowState.QUOTE_SERVICE
assert context.lifecycle.handoff_requested is False
assert context.lifecycle.callback_request_sent is False
assert context.customer.phone == ""
assert context.customer.callback_preference == ""

print("PASS 8 - Start New Quote resets handoff/callback lifecycle cleanly")


# ------------------------------------------------------------------
# 9. Direct callback before completed quote still creates a lead
# ------------------------------------------------------------------

context2 = ConversationContext(
    state=FlowState.QUOTE_COVERAGE
)
context2.metadata["sender_id"] = "customer-456"
context2.quote.service = "Wedding"
context2.quote.package = "Premium"

direct = runtime.handle_button(
    context=context2,
    payload="REQUEST_CALLBACK",
)

assert context2.state == FlowState.CALLBACK_PHONE
assert context2.lifecycle.active_lead_id
assert (
    FakeSheets.leads[
        context2.lifecycle.active_lead_id
    ]["status"]
    == "AWAITING_CALLBACK_PHONE"
)

print("PASS 9 - direct callback request can create a handoff lead before quote completion")


print()
print("=" * 72)
print("V3 BLOCK 10 HANDOFF + CALLBACK TEST PASSED")
print("=" * 72)
