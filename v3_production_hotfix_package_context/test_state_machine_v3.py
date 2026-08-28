from conversation_events import ConversationEvent, EventType
from conversation_models import ConversationContext, FlowState
from conversation_state_machine import (
    ConversationStateMachine,
    InvalidTransitionError,
)


def field_event(field_name: str, value):
    return ConversationEvent(
        type=EventType.FIELD_VALUE,
        field=field_name,
        value=value,
    )


machine = ConversationStateMachine()
context = ConversationContext()

# 1 Normal progression.
machine.handle(context, ConversationEvent(type=EventType.START_QUOTE))

for field_name, value, expected_state in [
    ("service", "Wedding", FlowState.QUOTE_PACKAGE),
    ("package", "Basic", FlowState.QUOTE_COVERAGE),
    ("coverage_type", "Both", FlowState.QUOTE_TRAVEL),
    ("travel_required", "No", FlowState.QUOTE_DURATION),
    ("duration_hours", 8, FlowState.QUOTE_DATE),
    ("event_date", "12 October", FlowState.QUOTE_LOCATION),
    ("location", "Birmingham", FlowState.QUOTE_READY),
]:
    result = machine.handle(context, field_event(field_name, value))
    assert context.quote.get(field_name) == value
    assert result.state == expected_state

print("PASS 1 - normal quote progression reaches QUOTE_READY")

# 2 Business interrupt.
context.reset_for_new_quote()
machine.handle(context, field_event("service", "Wedding"))
machine.handle(context, field_event("package", "Basic"))

assert context.state == FlowState.QUOTE_COVERAGE

machine.handle(
    context,
    ConversationEvent(
        type=EventType.BUSINESS_QUESTION,
        question_type="DRONE",
        question_text="Do you provide drone?",
    ),
)

assert context.state == FlowState.BUSINESS_INTERRUPT
assert context.resume_stack == [FlowState.QUOTE_COVERAGE]

result = machine.handle(
    context,
    ConversationEvent(type=EventType.BUSINESS_QUESTION_RESOLVED),
)

assert result.state == FlowState.QUOTE_COVERAGE
assert result.resume_prompt_required is True

print("PASS 2 - business question resumes exact interrupted state")

# 3 Package reconfirmation.
result = machine.handle(
    context,
    ConversationEvent(
        type=EventType.PACKAGE_RECONSIDERATION_REQUEST,
        question_text="Basic vs Premium?",
    ),
)

assert result.state == FlowState.PACKAGE_RECONFIRMATION
assert context.quote.package == "Basic"

result = machine.handle(
    context,
    ConversationEvent(
        type=EventType.SWITCH_PACKAGE,
        value="Premium",
    ),
)

assert context.quote.package == "Premium"
assert result.state == FlowState.QUOTE_COVERAGE

print("PASS 3 - package switch resumes coverage")

# 4 Side question during package decision.
context.quote.package = "Premium"
context.state = FlowState.QUOTE_COVERAGE

machine.handle(
    context,
    ConversationEvent(type=EventType.PACKAGE_RECONSIDERATION_REQUEST),
)
machine.handle(
    context,
    ConversationEvent(
        type=EventType.BUSINESS_QUESTION,
        question_type="PACKAGE_PRICING",
        question_text="Prices?",
    ),
)

assert context.resume_stack == [
    FlowState.QUOTE_COVERAGE,
    FlowState.PACKAGE_RECONFIRMATION,
]

machine.handle(
    context,
    ConversationEvent(type=EventType.BUSINESS_QUESTION_RESOLVED),
)
assert context.state == FlowState.PACKAGE_RECONFIRMATION

result = machine.handle(
    context,
    ConversationEvent(type=EventType.KEEP_CURRENT_PACKAGE),
)

assert result.state == FlowState.QUOTE_COVERAGE
assert context.quote.package == "Premium"

print("PASS 4 - side question returns to pending package decision")

# 5 Pause.
before_state = context.state
before_quote = context.quote.as_dict()

machine.handle(context, ConversationEvent(type=EventType.PAUSE))

assert context.state == before_state
assert context.quote.as_dict() == before_quote

print("PASS 5 - PAUSE cannot progress quote")

# 6 Defer travel.
context.reset_for_new_quote()

for field_name, value in [
    ("service", "Wedding"),
    ("package", "Premium"),
    ("coverage_type", "Both"),
]:
    machine.handle(context, field_event(field_name, value))

assert context.state == FlowState.QUOTE_TRAVEL

machine.handle(context, ConversationEvent(type=EventType.UNCLEAR))

assert context.deferred_fields == ["travel_required"]
assert context.state == FlowState.QUOTE_DURATION

for field_name, value in [
    ("duration_hours", 8),
    ("event_date", "12 October"),
    ("location", "Birmingham"),
]:
    machine.handle(context, field_event(field_name, value))

assert context.state == FlowState.DEFERRED_REVIEW

print("PASS 6 - unclear field is deferred")

# 7 Resolve deferred.
machine.handle(
    context,
    ConversationEvent(type=EventType.START_DEFERRED_REVIEW),
)

assert context.state == FlowState.QUOTE_TRAVEL
assert context.reviewing_deferred is True

machine.handle(context, field_event("travel_required", "Yes"))

assert context.state == FlowState.QUOTE_READY
assert context.deferred_fields == []
assert context.reviewing_deferred is False

print("PASS 7 - deferred review reaches QUOTE_READY")

# 8 Reject wrong field.
context.reset_for_new_quote()

try:
    machine.handle(context, field_event("package", "Premium"))
except InvalidTransitionError:
    pass
else:
    raise AssertionError("Expected field/state mismatch to fail.")

assert context.state == FlowState.QUOTE_SERVICE
assert context.quote.package is None

print("PASS 8 - wrong field cannot bypass state")

# 9 Quoted field change marks stale.
context.quote.service = "Wedding"
context.quote.package = "Basic"
context.quote_version = 1
context.quote_is_stale = False

machine.handle(
    context,
    ConversationEvent(
        type=EventType.CHANGE_FIELD,
        field="package",
        value="Premium",
    ),
)

assert context.quote.package == "Premium"
assert context.quote_is_stale is True

print("PASS 9 - changed quoted data becomes stale")

# 10 Transition log.
assert context.transition_log
assert context.transition_log[-1].event_type == EventType.CHANGE_FIELD.value

print("PASS 10 - transition log captured")

print()
print("=" * 72)
print("V3 BLOCK 1 STATE MACHINE TEST SUITE PASSED")
print("=" * 72)
