"""
Regression for the 17:03 transcript: typing instead of tapping.

    Hi
    Hi! How can we help you today?      <- IDLE, with buttons
    Wedding
    Sorry, something went wrong ...     <- crash, surfaced as the fallback

IDLE allowed only GREETING, START_NEW_QUOTE, BUSINESS_QUESTION, SPEAK_TO_TEAM,
REQUEST_CALLBACK and FINISH. A customer who typed what they wanted instead of
tapping "Get a Quote" produced an action Python did not permit, the semantic
adapter raised, and the turn failed.

Two fixes are covered here:
1. IDLE accepts a customer who opens with what they want, and starts the quote.
2. Any future gap of this kind degrades to a clarification instead of failing
   the turn, so a missing entry in STATE_ALLOWED_ACTIONS can never again reach
   a customer as an error.

Offline: fake Sheets knowledge, scripted interpreter, no Gemini, no network.
"""

from business_knowledge_adapter_v3 import BusinessKnowledgeAdapterV3
from conversation_models import ConversationContext, FlowState
from conversation_orchestrator import ConversationOrchestrator
from customer_response_renderer_v3 import CustomerResponseRendererV3
from gemini_semantic_adapter import GeminiSemanticAdapter
from semantic_contract import (
    SemanticAction,
    SemanticInterpretation,
    is_action_allowed,
)


class FakeKnowledge:
    @staticmethod
    def get_business_knowledge(force_refresh=False):
        return {
            "pricing": [
                {
                    "service": service,
                    "package": name,
                    "included_hours": 4,
                    "photography_price": 500,
                    "videography_price": 650,
                    "both_price": 950,
                    "extra_hour_rate": 80,
                    "travel_fee": 0,
                }
                for service in ("Wedding", "Birthday")
                for name in ("Basic", "Premium")
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
    meaning(SemanticAction.GREETING),
    meaning(SemanticAction.FIELD_VALUE, field_name="service", value="Wedding"),
])
context = ConversationContext()
orchestrator.handle_text(context=context, message_text="Hi")

assert context.state == FlowState.IDLE

turn = orchestrator.handle_text(context=context, message_text="Wedding")
text = renderer.render_plan(turn.response_plan).text

assert context.quote.service == "Wedding", "typing a service must start the quote"
assert context.state == FlowState.QUOTE_PACKAGE
assert "Basic" in text and "Premium" in text
print("PASS 1 - typing a service at IDLE starts the quote instead of failing")


# 2 -----------------------------------------------------------------
# Opening with a later detail must be kept, and service still asked for.
orchestrator = build([
    meaning(SemanticAction.FIELD_VALUE, field_name="duration_hours", value=8),
])
context = ConversationContext()

turn = orchestrator.handle_text(context=context, message_text="I need 8 hours")
text = renderer.render_plan(turn.response_plan).text

assert context.quote.duration_hours == 8, "the detail they gave must be kept"
assert context.quote.service is None
assert context.state == FlowState.QUOTE_SERVICE
assert "service" in text.lower(), "the flow must still ask for the service"
print("PASS 2 - opening with a later detail keeps it and still asks for service")


# 3 -----------------------------------------------------------------
# A value typed at IDLE is still checked against the approved catalogue.
orchestrator = build([
    meaning(SemanticAction.FIELD_VALUE, field_name="service", value="Skydiving"),
])
context = ConversationContext()

turn = orchestrator.handle_text(context=context, message_text="Skydiving")
text = renderer.render_plan(turn.response_plan).text

assert context.quote.service is None, "an unsupported service must not be stored"
assert "Skydiving" in text
assert "Wedding" in text and "Birthday" in text, "the real options must be offered"
print("PASS 3 - an unsupported service typed at IDLE is rejected with real options")


# 4 -----------------------------------------------------------------
# Correcting the field the flow is waiting on must move it forward.
orchestrator = build([
    meaning(SemanticAction.FIELD_VALUE, field_name="service", value="Wedding"),
    meaning(SemanticAction.FIELD_VALUE, field_name="package", value="Basic"),
    meaning(SemanticAction.CHANGE_FIELD, field_name="coverage_type", value="Both"),
])
context = ConversationContext()
orchestrator.handle_button(context=context, payload="GET_QUOTE")
orchestrator.handle_text(context=context, message_text="Wedding")
orchestrator.handle_text(context=context, message_text="Basic")

assert context.state == FlowState.QUOTE_COVERAGE

turn = orchestrator.handle_text(context=context, message_text="actually make it both")

assert context.quote.coverage_type == "Both"
assert context.state == FlowState.QUOTE_TRAVEL, (
    "answering the expected field as a correction must still advance the flow"
)
print("PASS 4 - a correction to the awaited field advances instead of re-asking")


# 5 -----------------------------------------------------------------
# The class of bug, not just this instance: a future gap must degrade.
adapter = GeminiSemanticAdapter(client=None)
context = ConversationContext()
context.state = FlowState.CALLBACK_PHONE

assert not is_action_allowed(context.state, SemanticAction.FIELD_VALUE)

interpretation = adapter.parse_response(
    context,
    {
        "action": "FIELD_VALUE",
        "field_name": "service",
        "value": "Wedding",
        "language": "English",
    },
)

assert interpretation.action == SemanticAction.UNCLEAR, (
    "a disallowed action must degrade, not raise"
)
assert interpretation.metadata.get("contract_gap") is True, (
    "the gap must be marked so it can be found in the logs"
)
print("PASS 5 - a contract gap degrades to a clarification instead of failing")


print()
print("=" * 72)
print("V3 IDLE ENTRY REGRESSION PASSED")
print("=" * 72)
