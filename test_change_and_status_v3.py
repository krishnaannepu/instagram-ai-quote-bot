"""
Regression for the 2026-08-28 production Instagram transcript.

Three defects, all reproduced from Cloud Run turn logs:

1. "change my package to Deluxe" was accepted. The catalogue guard existed
   for FIELD_VALUE but not for CHANGE_FIELD, so an invalid package entered
   quote state and only failed later at pricing.
2. Every change - valid, invalid, or a no-op - produced the identical reply
   ("Will travel be required for this booking?"). The customer had no way to
   know they had been heard.
3. "Which package am I in" was interpreted as PACKAGE_RECONSIDERATION, which
   pushed the conversation into PACKAGE_RECONFIRMATION and dumped a full price
   comparison. A question about current state must not mutate state.

Offline: fake Sheets knowledge, scripted interpreter, no Gemini.
Assertions check facts and state, never wording.
"""

from business_knowledge_adapter_v3 import BusinessKnowledgeAdapterV3
from conversation_events import EventType
from conversation_models import ConversationContext, FlowState
from conversation_orchestrator import ConversationOrchestrator
from customer_response_renderer_v3 import CustomerResponseRendererV3
from semantic_contract import SemanticAction, SemanticInterpretation


class FakeKnowledge:
    @staticmethod
    def get_business_knowledge(force_refresh=False):
        rows = [
            ("Basic", 4, 500, 650, 950, 80),
            ("Premium", 6, 700, 850, 1200, 100),
        ]
        return {
            "pricing": [
                {
                    "service": "Wedding",
                    "package": name,
                    "included_hours": inc,
                    "photography_price": photo,
                    "videography_price": video,
                    "both_price": both,
                    "extra_hour_rate": extra,
                    "travel_fee": 0,
                }
                for name, inc, photo, video, both, extra in rows
            ],
            "packages": [],
            "business_info": [],
            "faqs": [],
        }


class QueueInterpreter:
    def __init__(self, meanings):
        self.meanings = list(meanings)

    def interpret(self, context, message_text, **kwargs):
        if not self.meanings:
            raise AssertionError(
                f"No scripted interpretation remains for {message_text!r}"
            )
        return self.meanings.pop(0)


def meaning(action, **kwargs):
    return SemanticInterpretation(
        action=action,
        confidence=0.95,
        language="English",
        **kwargs,
    )


catalogue = BusinessKnowledgeAdapterV3(
    service_module=FakeKnowledge
).get_catalogue()

orchestrator = ConversationOrchestrator(
    semantic_interpreter=QueueInterpreter([
        meaning(SemanticAction.FIELD_VALUE, field_name="service", value="Wedding"),
        meaning(SemanticAction.FIELD_VALUE, field_name="package", value="Basic"),
        meaning(SemanticAction.FIELD_VALUE, field_name="coverage_type", value="Both"),
        meaning(SemanticAction.CHANGE_FIELD, field_name="package", value="Basic"),
        meaning(SemanticAction.STATUS_QUESTION,
                question_text="Which package am I in"),
        meaning(SemanticAction.CHANGE_FIELD, field_name="package", value="Deluxe"),
        meaning(SemanticAction.CHANGE_FIELD, field_name="package", value="Premium"),
    ]),
    supported_services=catalogue["supported_services"],
    packages_by_service=catalogue["packages_by_service"],
)

renderer = CustomerResponseRendererV3()
context = ConversationContext()

orchestrator.handle_button(context=context, payload="GET_QUOTE")
for message in ("Wedding", "Basic", "Both"):
    orchestrator.handle_text(context=context, message_text=message)

assert context.state == FlowState.QUOTE_TRAVEL
assert context.quote.package == "Basic"
print("SETUP  - Wedding / Basic / Both, waiting on travel")


# 1 -----------------------------------------------------------------
# A no-op change is still an answer and must be acknowledged.
turn = orchestrator.handle_text(
    context=context,
    message_text="Wait can you please change it to basic ..sorry",
)
text = renderer.render_plan(turn.response_plan).text

assert context.quote.package == "Basic"
assert context.state == FlowState.QUOTE_TRAVEL
assert "Basic" in text, "a no-op change must name the value it kept"
assert "travel" in text.lower(), "the outstanding question must still be asked"
print("PASS 1 - a no-op change is acknowledged, not silently swallowed")


# 2 -----------------------------------------------------------------
# A question about current state must not move the conversation.
turn = orchestrator.handle_text(context=context, message_text="Which package am I in")
text = renderer.render_plan(turn.response_plan).text

assert turn.event.type == EventType.STATUS_QUESTION
assert context.state == FlowState.QUOTE_TRAVEL, (
    "a read-only question must not enter PACKAGE_RECONFIRMATION"
)
assert context.resume_stack == [], "a status question must not push a resume frame"
assert context.quote.package == "Basic"
assert "Basic" in text, "the answer must name the selected package"
assert "Premium" not in text, "a status question must not become a price comparison"
assert "travel" in text.lower(), "the outstanding question must still be asked"
print("PASS 2 - a status question answers from state and changes nothing")


# 3 -----------------------------------------------------------------
# CHANGE_FIELD is guarded by the same catalogue as FIELD_VALUE.
turn = orchestrator.handle_text(
    context=context,
    message_text="change my package to Deluxe",
)
text = renderer.render_plan(turn.response_plan).text

assert turn.event.type == EventType.INVALID_FIELD_VALUE
assert context.quote.package == "Basic", "an invalid package must never be stored"
assert context.state == FlowState.QUOTE_TRAVEL
assert "Deluxe" in text, "the rejection must name what was rejected"
assert "Basic" in text and "Premium" in text, "the rejection must list the options"
assert "travel" in text.lower(), "the outstanding question must still be asked"
print("PASS 3 - an invalid package change is rejected and explained")


# 4 -----------------------------------------------------------------
turn = orchestrator.handle_text(context=context, message_text="change it to premium")
text = renderer.render_plan(turn.response_plan).text

assert context.quote.package == "Premium"
assert context.state == FlowState.QUOTE_TRAVEL
assert "Premium" in text, "a real change must be confirmed"
assert "travel" in text.lower(), "the outstanding question must still be asked"
print("PASS 4 - a valid change is applied and confirmed")


print()
print("=" * 72)
print("V3 CHANGE + STATUS REGRESSION PASSED")
print("=" * 72)
