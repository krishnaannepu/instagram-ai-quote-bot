"""
Regression for "Wait can I change something now" after a quote.

At EMAIL_CONFIRMATION the customer asked to change something without naming
what. Gemini returned CHANGE_FIELD with no field_name, the adapter raised
"CHANGE_FIELD requires field_name", and the turn failed.

The contract had no way to say "I want to change something, I have not said
what yet" - the same shape as the STATUS_QUESTION gap. CHANGE_REQUEST closes
it, and the adapter no longer decides that an incomplete interpretation is a
failure: Python routes it.

Runs through the REAL adapter via v3_test_harness.
"""

from conversation_models import ConversationContext, FlowState
from customer_response_renderer_v3 import CustomerResponseRendererV3
from v3_test_harness import build_orchestrator, gemini

renderer = CustomerResponseRendererV3()


def quoted_context(state=FlowState.EMAIL_CONFIRMATION):
    context = ConversationContext()
    context.state = state
    context.quote.service = "Wedding"
    context.quote.package = "Basic"
    context.quote.coverage_type = "Both"
    context.quote.travel_required = "Yes"
    context.quote.duration_hours = 8
    context.quote.event_date = "12th August"
    context.quote.location = "London"
    # A quote has already been produced, so a later change invalidates it.
    context.quote_version = 1
    return context


# 1 -----------------------------------------------------------------
orchestrator = build_orchestrator([gemini("CHANGE_FIELD")])
context = quoted_context()

turn = orchestrator.handle_text(
    context=context,
    message_text="Wait can I change something now",
)
text = renderer.render_plan(turn.response_plan).text

assert context.state == FlowState.EMAIL_CONFIRMATION, (
    "asking to change something must not move the conversation"
)
assert context.quote.package == "Basic", "nothing may change yet"
assert "Wedding" in text and "Basic" in text, (
    "the customer must be shown what there is to change"
)
print("PASS 1 - asking to change something lists the quote and changes nothing")


# 2 -----------------------------------------------------------------
orchestrator = build_orchestrator([gemini("CHANGE_FIELD", field_name="package")])
context = quoted_context()

turn = orchestrator.handle_text(context=context, message_text="the package")
text = renderer.render_plan(turn.response_plan).text

assert context.quote.package == "Basic", "naming a field is not yet a change"
assert context.state == FlowState.EMAIL_CONFIRMATION
assert "package" in text.lower()
assert "Basic" in text and "Premium" in text, "the real options must be offered"
print("PASS 2 - naming a field without a value asks what to change it to")


# 3 -----------------------------------------------------------------
orchestrator = build_orchestrator([
    gemini("CHANGE_FIELD", field_name="package", value="Premium"),
])
context = quoted_context()

turn = orchestrator.handle_text(context=context, message_text="make it premium")

assert context.quote.package == "Premium", "a complete change must be applied"
assert context.state == FlowState.QUOTE_READY, (
    "changing a priced detail must send the quote back to be recalculated"
)
assert context.quote_is_stale, "the old quote must be marked stale"
assert turn.response_plan.metadata.get("changed_field") == "package"
print("PASS 3 - a complete change is applied and re-prices the quote")


# 4 -----------------------------------------------------------------
# The same message must work mid-quote, not only after one.
orchestrator = build_orchestrator([gemini("CHANGE_FIELD")])
context = quoted_context(state=FlowState.QUOTE_TRAVEL)
context.quote.travel_required = None

turn = orchestrator.handle_text(context=context, message_text="can I change something")
text = renderer.render_plan(turn.response_plan).text

assert context.state == FlowState.QUOTE_TRAVEL
assert "Wedding" in text
print("PASS 4 - the same request works mid-quote, not only after a quote")


# 5 -----------------------------------------------------------------
# Two details in one message. One field_name slot cannot hold both, and
# picking one silently loses the other - which is what repeated the
# "what would you like to change" prompt instead of answering.
orchestrator = build_orchestrator([
    gemini("CHANGE_FIELD", changes=[
        {"field_name": "duration_hours", "value": 4},
        {"field_name": "coverage_type", "value": "Photography"},
    ]),
])
context = quoted_context(state=FlowState.POST_QUOTE)

turn = orchestrator.handle_text(
    context=context,
    message_text="duration is 4 hrs coverage is photography",
)
confirmation = renderer._change_confirmation(turn.response_plan) or ""

assert context.quote.duration_hours == 4, "the first detail must be applied"
assert context.quote.coverage_type == "Photography", (
    "the second detail must not be dropped"
)
assert context.state == FlowState.QUOTE_READY, "a priced change must re-price"
assert "4" in confirmation and "Photography" in confirmation, (
    "both changes must be confirmed"
)
print("PASS 5 - two details in one message are both applied and confirmed")


# 6 -----------------------------------------------------------------
# One good detail, one that is not in the catalogue. Keep the good one and
# say which one could not be used, rather than losing both or neither.
orchestrator = build_orchestrator([
    gemini("CHANGE_FIELD", changes=[
        {"field_name": "duration_hours", "value": 6},
        {"field_name": "package", "value": "Deluxe"},
    ]),
])
context = quoted_context(state=FlowState.POST_QUOTE)

turn = orchestrator.handle_text(
    context=context,
    message_text="6 hours and the deluxe package",
)
confirmation = renderer._change_confirmation(turn.response_plan) or ""

assert context.quote.duration_hours == 6, "the usable detail must be applied"
assert context.quote.package == "Basic", (
    "Deluxe is not a Wedding package and must not be stored"
)
assert "Deluxe" in confirmation, "the unusable detail must be named"
print("PASS 6 - a mixed message keeps what is valid and names what is not")


# 7 -----------------------------------------------------------------
# Mid-quote, several details including the one being asked for.
orchestrator = build_orchestrator([
    gemini("FIELD_VALUE", field_name="service", value="Wedding"),
    gemini("CHANGE_FIELD", changes=[
        {"field_name": "package", "value": "Premium"},
        {"field_name": "location", "value": "Bristol"},
    ]),
])
context = ConversationContext()
orchestrator.handle_button(context=context, payload="GET_QUOTE")
orchestrator.handle_text(context=context, message_text="Wedding")

assert context.state == FlowState.QUOTE_PACKAGE

orchestrator.handle_text(context=context, message_text="premium, and it's in Bristol")

assert context.quote.package == "Premium"
assert context.quote.location == "Bristol", "the extra detail must be kept"
assert context.state == FlowState.QUOTE_COVERAGE, (
    "answering the awaited field must still advance, even alongside extras"
)
print("PASS 7 - a multi-detail answer advances the flow and keeps the extras")


print()
print("=" * 72)
print("V3 CHANGE REQUEST REGRESSION PASSED")
print("=" * 72)
