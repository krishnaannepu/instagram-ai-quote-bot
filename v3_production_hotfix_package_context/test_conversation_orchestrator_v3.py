from conversation_models import (
    ConversationContext,
    FlowState,
)
from conversation_orchestrator import (
    ConversationOrchestrator,
    ConversationOrchestratorError,
)
from response_plan import ResponseAction
from semantic_contract import (
    SemanticAction,
    SemanticInterpretation,
)


class ScriptedInterpreter:
    """
    Offline semantic interpreter used only for orchestration tests.
    """

    def __init__(
        self,
        scripted_results,
    ):
        self.scripted_results = list(
            scripted_results
        )

    def interpret(
        self,
        context,
        message_text,
        **kwargs,
    ):
        if not self.scripted_results:
            raise RuntimeError(
                "No scripted semantic result remains."
            )

        return self.scripted_results.pop(0)


def meaning(
    action,
    *,
    field_name=None,
    value=None,
    question_type=None,
    question_text=None,
    language="English",
):
    return SemanticInterpretation(
        action=action,
        field_name=field_name,
        value=value,
        question_type=question_type,
        question_text=question_text,
        confidence=0.99,
        language=language,
    )


# ------------------------------------------------------------------
# TEST 1 - one orchestrator controls normal quote progression
# ------------------------------------------------------------------

interpreter = ScriptedInterpreter(
    [
        meaning(
            SemanticAction.FIELD_VALUE,
            field_name="service",
            value="Wedding",
        ),
        meaning(
            SemanticAction.FIELD_VALUE,
            field_name="package",
            value="Basic",
        ),
        meaning(
            SemanticAction.FIELD_VALUE,
            field_name="coverage_type",
            value="Both",
        ),
    ]
)

orchestrator = ConversationOrchestrator(
    semantic_interpreter=interpreter
)

context = ConversationContext()

start = orchestrator.handle_button(
    context=context,
    payload="GET_QUOTE",
)

assert start.response_plan.action == (
    ResponseAction.STARTED_NEW_QUOTE
)
assert start.response_plan.next_field == "service"
assert context.state == FlowState.QUOTE_SERVICE

result = orchestrator.handle_text(
    context=context,
    message_text="Wedding",
)

assert context.state == FlowState.QUOTE_PACKAGE
assert result.response_plan.action == ResponseAction.ASK_FIELD
assert result.response_plan.next_field == "package"

result = orchestrator.handle_text(
    context=context,
    message_text="basic kardo",
)

assert context.state == FlowState.QUOTE_COVERAGE
assert context.quote.package == "Basic"
assert result.response_plan.next_field == "coverage_type"

result = orchestrator.handle_text(
    context=context,
    message_text="both",
)

assert context.state == FlowState.QUOTE_TRAVEL
assert context.quote.coverage_type == "Both"
assert result.response_plan.next_field == "travel_required"

print("PASS 1 - normal text flow is controlled through one orchestrator")


# ------------------------------------------------------------------
# TEST 2 - business question creates an answer plan, not direct response
# ------------------------------------------------------------------

interpreter = ScriptedInterpreter(
    [
        meaning(
            SemanticAction.BUSINESS_QUESTION,
            question_type="DRONE",
            question_text="Do you provide drone?",
        )
    ]
)

orchestrator.semantic_interpreter = interpreter

before_state = context.state

result = orchestrator.handle_text(
    context=context,
    message_text="Do you provide drone?",
)

assert context.state == FlowState.BUSINESS_INTERRUPT
assert result.response_plan.action == (
    ResponseAction.ANSWER_BUSINESS_QUESTION
)
assert result.response_plan.business_question_type == "DRONE"
assert context.resume_stack == [before_state]

print("PASS 2 - business question becomes channel-independent answer plan")


# ------------------------------------------------------------------
# TEST 3 - resolving business question returns exact pending field
# ------------------------------------------------------------------

event = orchestrator.event_normalizer.from_semantic(
    context=context,
    interpretation=SemanticInterpretation(
        action=SemanticAction.PAUSE,
        confidence=1.0,
        language="English",
    ),
) if False else None

# The business-answer service will later call the state machine with the
# resolution event. Do it explicitly here.
from conversation_events import ConversationEvent, EventType

transition = orchestrator.state_machine.handle(
    context,
    ConversationEvent(
        type=EventType.BUSINESS_QUESTION_RESOLVED,
        metadata={
            "source": "business_answer_service"
        },
    ),
)

plan = orchestrator._plan_response(
    context=context,
    interpretation=None,
    event=ConversationEvent(
        type=EventType.BUSINESS_QUESTION_RESOLVED,
    ),
    transition=transition,
)

assert context.state == FlowState.QUOTE_TRAVEL
assert plan.action == ResponseAction.RESUME_FIELD
assert plan.next_field == "travel_required"

print("PASS 3 - business question resolution resumes exact field")


# ------------------------------------------------------------------
# TEST 4 - package reconsideration becomes package reconfirmation plan
# ------------------------------------------------------------------

context = ConversationContext(
    state=FlowState.QUOTE_COVERAGE
)
context.quote.service = "Wedding"
context.quote.package = "Basic"

interpreter = ScriptedInterpreter(
    [
        meaning(
            SemanticAction.PACKAGE_RECONSIDERATION,
            question_type="PACKAGE_COMPARISON",
            question_text="Basic vs Premium?",
        )
    ]
)

orchestrator.semantic_interpreter = interpreter

result = orchestrator.handle_text(
    context=context,
    message_text="tell me price difference",
)

assert context.state == FlowState.PACKAGE_RECONFIRMATION
assert result.response_plan.action == (
    ResponseAction.ASK_PACKAGE_RECONFIRMATION
)
assert result.response_plan.current_package == "Basic"
assert result.response_plan.options == [
    "Basic",
    "Premium",
]

print("PASS 4 - package reconsideration produces explicit reconfirmation plan")


# ------------------------------------------------------------------
# TEST 5 - bare okay cannot leave package reconfirmation
# ------------------------------------------------------------------

orchestrator.semantic_interpreter = ScriptedInterpreter(
    [
        meaning(
            SemanticAction.PAUSE
        )
    ]
)

result = orchestrator.handle_text(
    context=context,
    message_text="okay",
)

assert context.state == FlowState.PACKAGE_RECONFIRMATION
assert result.response_plan.action == (
    ResponseAction.WAIT_PACKAGE_RECONFIRMATION
)

print("PASS 5 - package pause cannot silently resume old field")


# ------------------------------------------------------------------
# TEST 6 - package switch resumes coverage
# ------------------------------------------------------------------

orchestrator.semantic_interpreter = ScriptedInterpreter(
    [
        meaning(
            SemanticAction.SWITCH_PACKAGE,
            value="Premium",
            language="Hinglish",
        )
    ]
)

result = orchestrator.handle_text(
    context=context,
    message_text="premium kardo",
)

assert context.quote.package == "Premium"
assert context.state == FlowState.QUOTE_COVERAGE
assert result.response_plan.action == ResponseAction.RESUME_FIELD
assert result.response_plan.next_field == "coverage_type"

print("PASS 6 - package switch resumes exact interrupted field")


# ------------------------------------------------------------------
# TEST 7 - uncertainty defers and asks next field
# ------------------------------------------------------------------

context = ConversationContext(
    state=FlowState.QUOTE_TRAVEL
)
context.quote.service = "Wedding"
context.quote.package = "Premium"
context.quote.coverage_type = "Both"

orchestrator.semantic_interpreter = ScriptedInterpreter(
    [
        meaning(
            SemanticAction.UNCLEAR
        )
    ]
)

result = orchestrator.handle_text(
    context=context,
    message_text="maybe",
)

assert context.deferred_fields == ["travel_required"]
assert context.state == FlowState.QUOTE_DURATION
assert result.response_plan.action == ResponseAction.ASK_FIELD
assert result.response_plan.next_field == "duration_hours"

print("PASS 7 - uncertainty defers current field and continues")


# ------------------------------------------------------------------
# TEST 8 - structured turn log records before/interpretation/event/after
# ------------------------------------------------------------------

log_record = result.turn_log

assert log_record["before"]["state"] == "QUOTE_TRAVEL"
assert log_record["interpretation"]["action"] == "UNCLEAR"
assert log_record["event"]["type"] == "UNCLEAR"
assert log_record["after"]["state"] == "QUOTE_DURATION"
assert (
    log_record["response_plan"]["next_field"]
    == "duration_hours"
)

print("PASS 8 - every orchestrated turn has structured diagnostics")


# ------------------------------------------------------------------
# TEST 9 - invalid interpretation cannot silently mutate state
# ------------------------------------------------------------------

context = ConversationContext(
    state=FlowState.QUOTE_COVERAGE
)
context.quote.service = "Wedding"
context.quote.package = "Basic"

before_quote = context.quote.as_dict()

orchestrator.semantic_interpreter = ScriptedInterpreter(
    [
        meaning(
            SemanticAction.FIELD_VALUE,
            field_name="package",
            value="Premium",
        )
    ]
)

try:
    orchestrator.handle_text(
        context=context,
        message_text="premium",
    )
except ConversationOrchestratorError as error:
    assert error.turn_log["error"]
else:
    raise AssertionError(
        "Invalid semantic field must fail orchestration."
    )

assert context.state == FlowState.QUOTE_COVERAGE
assert context.quote.as_dict() == before_quote

print("PASS 9 - invalid interpretation cannot mutate authoritative context")


# ------------------------------------------------------------------
# TEST 10 - button and text both enter state machine via orchestrator
# ------------------------------------------------------------------

context = ConversationContext(
    state=FlowState.QUOTE_PACKAGE
)
context.quote.service = "Wedding"

button_result = orchestrator.handle_button(
    context=context,
    payload="PACKAGE_BASIC",
)

assert button_result.event.type.value == "FIELD_VALUE"
assert button_result.event.field == "package"
assert button_result.event.value == "Basic"
assert context.state == FlowState.QUOTE_COVERAGE

print("PASS 10 - buttons no longer need a separate state-transition service")

print()
print("=" * 72)
print("V3 BLOCK 5 ORCHESTRATOR TEST SUITE PASSED")
print("=" * 72)
