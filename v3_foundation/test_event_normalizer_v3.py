from conversation_events import ConversationEvent, EventType
from conversation_models import ConversationContext, FlowState
from conversation_state_machine import ConversationStateMachine
from event_normalizer import (
    EventNormalizer,
    EventNormalizationError,
)
from semantic_contract import (
    SemanticAction,
    SemanticInterpretation,
)


normalizer = EventNormalizer()
machine = ConversationStateMachine()
context = ConversationContext()


def semantic(
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


# ------------------------------------------------------------------
# TEST 1 - GET_QUOTE button becomes START_QUOTE event
# ------------------------------------------------------------------

event = normalizer.from_button(
    context,
    "GET_QUOTE",
)

assert event.type == EventType.START_QUOTE

machine.handle(
    context,
    event,
)

assert context.state == FlowState.QUOTE_SERVICE

print("PASS 1 - GET_QUOTE button normalizes to START_QUOTE")


# ------------------------------------------------------------------
# TEST 2 - service button and semantic interpretation produce
# the same business event
# ------------------------------------------------------------------

button_event = normalizer.from_button(
    context,
    "SERVICE_WEDDING",
)

semantic_event = normalizer.from_semantic(
    context,
    semantic(
        SemanticAction.FIELD_VALUE,
        field_name="service",
        value="Wedding",
    ),
)

assert button_event.type == semantic_event.type
assert button_event.field == semantic_event.field
assert button_event.value == semantic_event.value

machine.handle(
    context,
    semantic_event,
)

assert context.state == FlowState.QUOTE_PACKAGE

print("PASS 2 - service button and typed meaning become same event")


# ------------------------------------------------------------------
# TEST 3 - package click and future Gemini result are identical
# ------------------------------------------------------------------

button_event = normalizer.from_button(
    context,
    "PACKAGE_BASIC",
)

semantic_event = normalizer.from_semantic(
    context,
    semantic(
        SemanticAction.FIELD_VALUE,
        field_name="package",
        value="Basic",
    ),
)

assert (
    button_event.type,
    button_event.field,
    button_event.value,
) == (
    semantic_event.type,
    semantic_event.field,
    semantic_event.value,
)

machine.handle(
    context,
    semantic_event,
)

assert context.quote.package == "Basic"
assert context.state == FlowState.QUOTE_COVERAGE

print("PASS 3 - Basic button and 'basic kardo' contract are identical")


# ------------------------------------------------------------------
# TEST 4 - bare Both while coverage is expected cannot become
# a package event
# ------------------------------------------------------------------

button_event = normalizer.from_button(
    context,
    "COVERAGE_BOTH",
)

semantic_event = normalizer.from_semantic(
    context,
    semantic(
        SemanticAction.FIELD_VALUE,
        field_name="coverage_type",
        value="Both",
    ),
)

assert button_event.field == "coverage_type"
assert semantic_event.field == "coverage_type"
assert semantic_event.value == "Both"

machine.handle(
    context,
    semantic_event,
)

assert context.quote.coverage_type == "Both"
assert context.state == FlowState.QUOTE_TRAVEL

print("PASS 4 - Both is coverage while coverage state is authoritative")


# ------------------------------------------------------------------
# TEST 5 - wrong button for current state is rejected
# ------------------------------------------------------------------

try:
    normalizer.from_button(
        context,
        "PACKAGE_PREMIUM",
    )
except EventNormalizationError:
    pass
else:
    raise AssertionError(
        "Package button should be invalid while travel is expected."
    )

assert context.state == FlowState.QUOTE_TRAVEL
assert context.quote.package == "Basic"

print("PASS 5 - stale/wrong button cannot mutate another state")


# ------------------------------------------------------------------
# TEST 6 - Travel Yes button and semantic Yes are identical
# ------------------------------------------------------------------

button_event = normalizer.from_button(
    context,
    "TRAVEL_YES",
)

semantic_event = normalizer.from_semantic(
    context,
    semantic(
        SemanticAction.FIELD_VALUE,
        field_name="travel_required",
        value="Yes",
    ),
)

assert (
    button_event.type,
    button_event.field,
    button_event.value,
) == (
    semantic_event.type,
    semantic_event.field,
    semantic_event.value,
)

machine.handle(
    context,
    semantic_event,
)

assert context.quote.travel_required == "Yes"
assert context.state == FlowState.QUOTE_DURATION

print("PASS 6 - travel button and natural affirmative share one path")


# ------------------------------------------------------------------
# TEST 7 - business question becomes generic interrupt
# ------------------------------------------------------------------

business_event = normalizer.from_semantic(
    context,
    semantic(
        SemanticAction.BUSINESS_QUESTION,
        question_type="DRONE",
        question_text="Do you provide drone?",
    ),
)

assert business_event.type == EventType.BUSINESS_QUESTION

machine.handle(
    context,
    business_event,
)

assert context.state == FlowState.BUSINESS_INTERRUPT
assert context.resume_stack == [
    FlowState.QUOTE_DURATION
]

machine.handle(
    context,
    ConversationEvent(
        type=EventType.BUSINESS_QUESTION_RESOLVED,
    ),
)

assert context.state == FlowState.QUOTE_DURATION

print("PASS 7 - business question interrupt is source-independent")


# ------------------------------------------------------------------
# TEST 8 - package reconsideration contract is only valid after
# a package already exists
# ------------------------------------------------------------------

reconsider_event = normalizer.from_semantic(
    context,
    semantic(
        SemanticAction.PACKAGE_RECONSIDERATION,
        question_type="PACKAGE_COMPARISON",
        question_text="Basic vs Premium?",
    ),
)

assert (
    reconsider_event.type
    == EventType.PACKAGE_RECONSIDERATION_REQUEST
)

machine.handle(
    context,
    reconsider_event,
)

assert context.state == FlowState.PACKAGE_RECONFIRMATION

print("PASS 8 - package comparison becomes explicit reconsideration event")


# ------------------------------------------------------------------
# TEST 9 - keep/switch contract is constrained by reconfirmation state
# ------------------------------------------------------------------

switch_event = normalizer.from_semantic(
    context,
    semantic(
        SemanticAction.SWITCH_PACKAGE,
        value="Premium",
    ),
)

assert switch_event.type == EventType.SWITCH_PACKAGE
assert switch_event.value == "Premium"

machine.handle(
    context,
    switch_event,
)

assert context.quote.package == "Premium"
assert context.state == FlowState.QUOTE_DURATION

print("PASS 9 - package switch resumes exact previous state")


# ------------------------------------------------------------------
# TEST 10 - semantic action not allowed in a state is rejected
# ------------------------------------------------------------------

try:
    normalizer.from_semantic(
        context,
        semantic(
            SemanticAction.KEEP_CURRENT_PACKAGE,
        ),
    )
except EventNormalizationError:
    pass
else:
    raise AssertionError(
        "KEEP_CURRENT_PACKAGE must fail outside reconfirmation."
    )

print("PASS 10 - state-specific semantic contract rejects invalid actions")


# ------------------------------------------------------------------
# TEST 11 - source metadata differs, business event does not
# ------------------------------------------------------------------

context = ConversationContext(
    state=FlowState.QUOTE_PACKAGE
)

button_event = normalizer.from_button(
    context,
    "PACKAGE_PREMIUM",
)

semantic_event = normalizer.from_semantic(
    context,
    semantic(
        SemanticAction.FIELD_VALUE,
        field_name="package",
        value="Premium",
    ),
)

assert button_event.metadata["source"] == "button"
assert semantic_event.metadata["source"] == "semantic"

assert (
    button_event.type,
    button_event.field,
    button_event.value,
) == (
    semantic_event.type,
    semantic_event.field,
    semantic_event.value,
)

print("PASS 11 - source is metadata only; business event is identical")

print()
print("=" * 72)
print("V3 BLOCK 2 EVENT NORMALIZATION TEST SUITE PASSED")
print("=" * 72)
