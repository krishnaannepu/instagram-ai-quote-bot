from conversation_events import (
    ConversationEvent,
    EventType,
)
from conversation_models import (
    ConversationContext,
    FlowState,
)
from conversation_orchestrator import (
    ConversationOrchestrator,
)
from response_plan import ResponseAction
from semantic_contract import (
    SemanticAction,
    SemanticInterpretation,
)


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
        return self.meanings.pop(0)


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


meanings = [
    m(
        SemanticAction.FIELD_VALUE,
        "service",
        "Wedding",
    ),
    m(
        SemanticAction.FIELD_VALUE,
        "package",
        "Basic",
    ),
    m(
        SemanticAction.PACKAGE_RECONSIDERATION,
        question_type="PACKAGE_COMPARISON",
        question_text="Basic vs Premium?",
    ),
    m(
        SemanticAction.BUSINESS_QUESTION,
        question_type="PACKAGE_PRICING",
        question_text="Prices?",
    ),
    m(
        SemanticAction.PAUSE,
    ),
    m(
        SemanticAction.SWITCH_PACKAGE,
        value="Premium",
    ),
    m(
        SemanticAction.FIELD_VALUE,
        "coverage_type",
        "Both",
    ),
    m(
        SemanticAction.UNCLEAR,
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
    m(
        SemanticAction.START_DEFERRED_REVIEW,
    ),
    m(
        SemanticAction.FIELD_VALUE,
        "travel_required",
        "Yes",
    ),
]

orchestrator = ConversationOrchestrator(
    semantic_interpreter=
        QueueInterpreter(
            meanings
        )
)

context = ConversationContext()

orchestrator.handle_button(
    context=context,
    payload="GET_QUOTE",
)

orchestrator.handle_text(
    context=context,
    message_text="Wedding",
)

orchestrator.handle_text(
    context=context,
    message_text="Basic",
)

# Package comparison.
result = orchestrator.handle_text(
    context=context,
    message_text="What is the difference?",
)

assert result.response_plan.action == (
    ResponseAction
    .ASK_PACKAGE_RECONFIRMATION
)

# Side question inside pending package decision.
result = orchestrator.handle_text(
    context=context,
    message_text="Prices?",
)

assert result.response_plan.action == (
    ResponseAction
    .ANSWER_BUSINESS_QUESTION
)
assert context.state == FlowState.BUSINESS_INTERRUPT

# Simulate business-answer service completing the interrupt.
transition = orchestrator.state_machine.handle(
    context,
    ConversationEvent(
        type=
            EventType
            .BUSINESS_QUESTION_RESOLVED,
    ),
)

plan = orchestrator._plan_response(
    context=context,
    interpretation=None,
    event=ConversationEvent(
        type=
            EventType
            .BUSINESS_QUESTION_RESOLVED,
    ),
    transition=transition,
)

assert (
    plan.action
    == ResponseAction
    .ASK_PACKAGE_RECONFIRMATION
)
assert context.state == FlowState.PACKAGE_RECONFIRMATION

# Bare okay must stay.
result = orchestrator.handle_text(
    context=context,
    message_text="okay",
)

assert result.response_plan.action == (
    ResponseAction
    .WAIT_PACKAGE_RECONFIRMATION
)

# Switch.
result = orchestrator.handle_text(
    context=context,
    message_text="Premium kardo",
)

assert context.quote.package == "Premium"
assert context.state == FlowState.QUOTE_COVERAGE

# Coverage.
orchestrator.handle_text(
    context=context,
    message_text="both",
)

# Travel uncertain -> defer.
orchestrator.handle_text(
    context=context,
    message_text="maybe",
)

assert context.deferred_fields == ["travel_required"]

# Continue remaining fields.
orchestrator.handle_text(
    context=context,
    message_text="8",
)

orchestrator.handle_text(
    context=context,
    message_text="12 October",
)

result = orchestrator.handle_text(
    context=context,
    message_text="Birmingham",
)

assert (
    context.state
    == FlowState.DEFERRED_REVIEW
)
assert (
    result.response_plan.action
    == ResponseAction.REVIEW_DEFERRED_FIELDS
)

# Ready.
result = orchestrator.handle_text(
    context=context,
    message_text="okay kardo",
)

assert context.state == FlowState.QUOTE_TRAVEL

# Resolve travel.
result = orchestrator.handle_text(
    context=context,
    message_text="yes",
)

assert context.state == FlowState.QUOTE_READY
assert result.response_plan.action == ResponseAction.QUOTE_READY

assert context.quote.as_dict() == {
    "service": "Wedding",
    "package": "Premium",
    "coverage_type": "Both",
    "travel_required": "Yes",
    "duration_hours": 8,
    "event_date": "12 October",
    "location": "Birmingham",
}

print("PASS 1 - complete interrupted conversation reaches QUOTE_READY")
print("PASS 2 - selected package is Premium after reconsideration")
print("PASS 3 - side pricing question did not erase package decision")
print("PASS 4 - uncertain travel was deferred and later resolved")
print("PASS 5 - no legacy current_stage/expected_quote_field is required")

print()
print("=" * 72)
print("V3 BLOCK 5 FULL CONVERSATION SIMULATION PASSED")
print("=" * 72)
