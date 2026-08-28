"""
Regression for the 2026-08-28 "Sorry it's wedding" transcript.

At QUOTE_PACKAGE the customer corrected the service they had already given.
CHANGE_FIELD was not in the allowed action set for QUOTE_SERVICE or
QUOTE_PACKAGE, so the semantic adapter raised, main.py returned HTTP 500, and
the customer received nothing at all while Meta retried the same message.

Covers:
1. a service correction is accepted at QUOTE_PACKAGE
2. a service correction that strands the package clears it and rewinds
3. a failing turn still answers the customer instead of going silent

Offline: fake Sheets knowledge, scripted interpreter, no Gemini, no network.
"""

from business_knowledge_adapter_v3 import BusinessKnowledgeAdapterV3
from conversation_models import ConversationContext, FlowState
from conversation_orchestrator import ConversationOrchestrator
from customer_response_renderer_v3 import CustomerResponseRendererV3
from instagram_channel_adapter_v3 import InstagramChannelAdapterV3
from meta_webhook_parser_v3 import IncomingMessageType
from semantic_contract import (
    SemanticAction,
    SemanticInterpretation,
    is_action_allowed,
)


# Birthday carries a package Wedding does not, so a service correction can
# genuinely strand the current selection.
CATALOGUE = {
    "Wedding": [("Basic", 4, 500, 650, 950, 80),
                ("Premium", 6, 700, 850, 1200, 100)],
    "Birthday": [("Basic", 3, 300, 400, 600, 60),
                 ("Deluxe", 5, 550, 700, 1000, 90)],
}


class FakeKnowledge:
    @staticmethod
    def get_business_knowledge(force_refresh=False):
        return {
            "pricing": [
                {
                    "service": service,
                    "package": name,
                    "included_hours": inc,
                    "photography_price": photo,
                    "videography_price": video,
                    "both_price": both,
                    "extra_hour_rate": extra,
                    "travel_fee": 0,
                }
                for service, rows in CATALOGUE.items()
                for name, inc, photo, video, both, extra in rows
            ],
            "packages": [],
            "business_info": [],
            "faqs": [],
        }


class GatedInterpreter:
    """Mirrors the real adapter: a disallowed action raises, as in production."""

    def __init__(self, meanings):
        self.meanings = list(meanings)

    def interpret(self, context, message_text, **kwargs):
        if not self.meanings:
            raise AssertionError(
                f"No scripted interpretation remains for {message_text!r}"
            )

        meaning = self.meanings.pop(0)

        if not is_action_allowed(context.state, meaning.action):
            raise RuntimeError(
                f"Action {meaning.action.value} is not allowed "
                f"while state is {context.state.value}."
            )

        return meaning


def meaning(action, **kwargs):
    return SemanticInterpretation(
        action=action,
        confidence=0.95,
        language="English",
        **kwargs,
    )


def build(meanings):
    catalogue = BusinessKnowledgeAdapterV3(
        service_module=FakeKnowledge
    ).get_catalogue()

    return ConversationOrchestrator(
        semantic_interpreter=GatedInterpreter(meanings),
        supported_services=catalogue["supported_services"],
        packages_by_service=catalogue["packages_by_service"],
    )


renderer = CustomerResponseRendererV3()


# 1 -----------------------------------------------------------------
orchestrator = build([
    meaning(SemanticAction.FIELD_VALUE, field_name="service", value="Birthday"),
    meaning(SemanticAction.CHANGE_FIELD, field_name="service", value="Wedding"),
])
context = ConversationContext()
orchestrator.handle_button(context=context, payload="GET_QUOTE")
orchestrator.handle_text(context=context, message_text="Birthday")

assert context.state == FlowState.QUOTE_PACKAGE
assert context.quote.service == "Birthday"

turn = orchestrator.handle_text(context=context, message_text="Sorry it's wedding")
text = renderer.render_plan(turn.response_plan).text

assert context.quote.service == "Wedding", "the correction must be applied"
assert context.state == FlowState.QUOTE_PACKAGE
assert "Wedding" in text, "the correction must be acknowledged"
assert "Basic" in text and "Premium" in text, (
    "the package options must come from the corrected service"
)
assert "Deluxe" not in text, "options must not leak from the old service"
print("PASS 1 - a service correction at QUOTE_PACKAGE is applied and confirmed")


# 2 -----------------------------------------------------------------
orchestrator = build([
    meaning(SemanticAction.FIELD_VALUE, field_name="service", value="Birthday"),
    meaning(SemanticAction.FIELD_VALUE, field_name="package", value="Deluxe"),
    meaning(SemanticAction.FIELD_VALUE, field_name="coverage_type", value="Both"),
    meaning(SemanticAction.CHANGE_FIELD, field_name="service", value="Wedding"),
])
context = ConversationContext()
orchestrator.handle_button(context=context, payload="GET_QUOTE")
for message in ("Birthday", "Deluxe", "Both"):
    orchestrator.handle_text(context=context, message_text=message)

assert context.state == FlowState.QUOTE_TRAVEL
assert context.quote.package == "Deluxe"

turn = orchestrator.handle_text(context=context, message_text="actually make it a wedding")
text = renderer.render_plan(turn.response_plan).text

assert context.quote.service == "Wedding"
assert context.quote.package is None, (
    "Deluxe does not exist for Wedding and must not survive the change"
)
assert context.state == FlowState.QUOTE_PACKAGE, (
    "the flow must rewind to the field that has to be answered again"
)
assert "Basic" in text and "Premium" in text
print("PASS 2 - a stranded package is cleared and the flow rewinds to it")


# 3 -----------------------------------------------------------------
class ExplodingRuntime:
    def handle_text(self, **kwargs):
        raise RuntimeError("simulated interpreter failure")

    def handle_button(self, **kwargs):
        raise RuntimeError("simulated interpreter failure")


class RecordingSender:
    def __init__(self):
        self.sent = []

    def send_rendered(self, *, recipient_id, message):
        self.sent.append(message)


class MemoryRepo:
    def __init__(self):
        self.store = {}

    def get(self, sender_id):
        return self.store.setdefault(sender_id, ConversationContext())

    def save(self, sender_id, context):
        self.store[sender_id] = context


class OneMessage:
    sender_id = "IG-1"
    message_id = "mid-1"
    type = IncomingMessageType.TEXT
    text = "Sorry it's wedding"
    button_payload = None


class FakeParser:
    def parse(self, payload):
        return [OneMessage()]


sender = RecordingSender()
channel = InstagramChannelAdapterV3(
    runtime=ExplodingRuntime(),
    session_repository=MemoryRepo(),
    sender=sender,
    parser=FakeParser(),
)

result = channel.process_webhook({})

assert result.failed_messages == 1
assert result.processed_messages == 0
assert len(sender.sent) == 1, "a failed turn must still answer the customer"
assert sender.sent[0].text.strip(), "the fallback must not be empty"
assert any(b.payload == "SPEAK_TO_TEAM" for b in sender.sent[0].buttons), (
    "a failed turn must offer a human"
)
print("PASS 3 - a failing turn answers the customer instead of going silent")


print()
print("=" * 72)
print("V3 SERVICE CORRECTION REGRESSION PASSED")
print("=" * 72)
