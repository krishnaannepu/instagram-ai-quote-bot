"""
Regression for the 17:03 transcript: typing instead of tapping.

    Hi
    Hi! How can we help you today?      <- IDLE, with buttons
    Wedding
    Sorry, something went wrong ...

Two separate gates rejected this. IDLE did not allow FIELD_VALUE, and the
adapter separately required FIELD_VALUE to target the state's expected field,
which IDLE does not have.

The first fix alone did not work, because the first version of this test used
a hand-rolled interpreter that only mirrored gate one. Every scenario here now
runs through the REAL GeminiSemanticAdapter via v3_test_harness, so a gate
cannot hide from the test again.
"""

from conversation_models import ConversationContext, FlowState
from customer_response_renderer_v3 import CustomerResponseRendererV3
from v3_test_harness import build_orchestrator, gemini

renderer = CustomerResponseRendererV3()


# 1 -----------------------------------------------------------------
orchestrator = build_orchestrator([
    gemini("GREETING"),
    gemini("FIELD_VALUE", field_name="service", value="Wedding"),
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
orchestrator = build_orchestrator([
    gemini("FIELD_VALUE", field_name="duration_hours", value=8),
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
orchestrator = build_orchestrator([
    gemini("FIELD_VALUE", field_name="service", value="Skydiving"),
])
context = ConversationContext()

turn = orchestrator.handle_text(context=context, message_text="Skydiving")
text = renderer.render_plan(turn.response_plan).text

assert context.quote.service is None, "an unsupported service must not be stored"
assert "Skydiving" in text
assert "Wedding" in text and "Birthday" in text, "the real options must be offered"
print("PASS 3 - an unsupported service typed at IDLE is rejected with real options")


# 4 -----------------------------------------------------------------
orchestrator = build_orchestrator([
    gemini("FIELD_VALUE", field_name="service", value="Wedding"),
    gemini("FIELD_VALUE", field_name="package", value="Basic"),
    gemini("CHANGE_FIELD", field_name="coverage_type", value="Both"),
])
context = ConversationContext()
orchestrator.handle_button(context=context, payload="GET_QUOTE")
orchestrator.handle_text(context=context, message_text="Wedding")
orchestrator.handle_text(context=context, message_text="Basic")

assert context.state == FlowState.QUOTE_COVERAGE

orchestrator.handle_text(context=context, message_text="actually make it both")

assert context.quote.coverage_type == "Both"
assert context.state == FlowState.QUOTE_TRAVEL, (
    "answering the expected field as a correction must still advance the flow"
)
print("PASS 4 - a correction to the awaited field advances instead of re-asking")


# 5 -----------------------------------------------------------------
# A value volunteered out of sequence is recorded, not rejected, and the
# question the flow is actually waiting on is still asked.
orchestrator = build_orchestrator([
    gemini("FIELD_VALUE", field_name="service", value="Wedding"),
    gemini("FIELD_VALUE", field_name="location", value="Birmingham"),
])
context = ConversationContext()
orchestrator.handle_button(context=context, payload="GET_QUOTE")
orchestrator.handle_text(context=context, message_text="Wedding")

assert context.state == FlowState.QUOTE_PACKAGE

turn = orchestrator.handle_text(context=context, message_text="it's in Birmingham")
text = renderer.render_plan(turn.response_plan).text

assert context.quote.location == "Birmingham", "the volunteered detail is kept"
assert context.state == FlowState.QUOTE_PACKAGE, "the flow does not skip ahead"
assert "Basic" in text and "Premium" in text, "the awaited question is repeated"
print("PASS 5 - a detail given out of sequence is kept without derailing the flow")


print()
print("=" * 72)
print("V3 IDLE ENTRY REGRESSION PASSED")
print("=" * 72)
