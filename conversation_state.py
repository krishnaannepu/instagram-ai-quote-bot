from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any


class FlowState(str, Enum):
    """Authoritative AI-quote conversation states.

    ``current_stage`` in ``main.py`` remains the outer channel/UI stage
    (email collection, callback collection, post-quote menu, etc.).
    ``flow_state`` owns only the natural-language quote conversation.
    """

    IDLE = "IDLE"
    QUOTE_SERVICE = "QUOTE_SERVICE"
    QUOTE_PACKAGE = "QUOTE_PACKAGE"
    QUOTE_COVERAGE = "QUOTE_COVERAGE"
    QUOTE_TRAVEL = "QUOTE_TRAVEL"
    QUOTE_DURATION = "QUOTE_DURATION"
    QUOTE_DATE = "QUOTE_DATE"
    QUOTE_LOCATION = "QUOTE_LOCATION"
    DEFERRED_REVIEW_READY = "DEFERRED_REVIEW_READY"
    PACKAGE_RECONFIRMATION = "PACKAGE_RECONFIRMATION"
    QUOTE_READY = "QUOTE_READY"
    FINISHED = "FINISHED"


FIELD_TO_STATE = {
    "service": FlowState.QUOTE_SERVICE,
    "package": FlowState.QUOTE_PACKAGE,
    "coverage_type": FlowState.QUOTE_COVERAGE,
    "travel_required": FlowState.QUOTE_TRAVEL,
    "duration_hours": FlowState.QUOTE_DURATION,
    "event_date": FlowState.QUOTE_DATE,
    "location": FlowState.QUOTE_LOCATION,
}

STATE_TO_FIELD = {
    state.value: field_name
    for field_name, state in FIELD_TO_STATE.items()
}


QUOTE_STATES = set(STATE_TO_FIELD)


def state_value(value: Any) -> str:
    if isinstance(value, FlowState):
        return value.value

    cleaned = str(value or "").strip().upper()

    if cleaned in {state.value for state in FlowState}:
        return cleaned

    return ""


def get_flow_state(session: dict) -> str:
    return state_value(session.get("flow_state"))


def expected_field_for_state(state: str | FlowState) -> str | None:
    return STATE_TO_FIELD.get(state_value(state))


def state_for_field(field_name: str | None) -> str:
    if not field_name:
        return ""

    state = FIELD_TO_STATE.get(str(field_name).strip())
    return state.value if state else ""


def _transition_log(session: dict) -> list[dict]:
    log = session.get("transition_log")

    if not isinstance(log, list):
        log = []
        session["transition_log"] = log

    return log


def transition(
    session: dict,
    new_state: str | FlowState,
    reason: str,
) -> str:
    """Move to one authoritative flow state and record the transition."""

    new_value = state_value(new_state)

    if not new_value:
        raise ValueError(f"Unknown flow state: {new_state}")

    old_value = get_flow_state(session) or FlowState.IDLE.value
    session["flow_state"] = new_value

    # Compatibility for older code that still reads expected_quote_field.
    session["expected_quote_field"] = (
        expected_field_for_state(new_value)
        or ""
    )

    if old_value != new_value:
        log = _transition_log(session)
        log.append(
            {
                "at": datetime.now(timezone.utc).isoformat(),
                "from": old_value,
                "to": new_value,
                "reason": str(reason or "").strip(),
            }
        )
        del log[:-40]

    return new_value


def _resume_stack(session: dict) -> list[str]:
    stack = session.get("resume_stack")

    if not isinstance(stack, list):
        stack = []
        session["resume_stack"] = stack

    return stack


def push_resume_state(
    session: dict,
    state: str | FlowState | None = None,
) -> None:
    value = state_value(state or get_flow_state(session))

    if not value:
        return

    stack = _resume_stack(session)

    # Avoid duplicate frames from repeated side questions.
    if not stack or stack[-1] != value:
        stack.append(value)

    del stack[:-10]


def pop_resume_state(
    session: dict,
    default: str | FlowState = FlowState.IDLE,
) -> str:
    stack = _resume_stack(session)

    if stack:
        value = state_value(stack.pop())
        if value:
            return value

    return state_value(default) or FlowState.IDLE.value


def clear_resume_stack(session: dict) -> None:
    session["resume_stack"] = []


def initialize_flow_state(
    session: dict,
    *,
    quote_fields: tuple[str, ...],
    missing_fields: list[str],
    deferred_fields: list[str],
) -> str:
    """Recover a sensible V2 state for an old/in-memory session.

    This makes deployment backwards-compatible with sessions created before
    the state-machine fields existed.
    """

    current = get_flow_state(session)

    if current:
        transition(session, current, "state already initialized")
        return current

    if not missing_fields and any(
        session.get(field_name)
        for field_name in quote_fields
    ):
        return transition(
            session,
            FlowState.QUOTE_READY,
            "recovered complete quote",
        )

    deferred = set(deferred_fields)

    for field_name in missing_fields:
        if field_name not in deferred:
            return transition(
                session,
                state_for_field(field_name),
                "recovered next missing quote field",
            )

    if missing_fields:
        return transition(
            session,
            FlowState.DEFERRED_REVIEW_READY,
            "recovered deferred review",
        )

    return transition(
        session,
        FlowState.IDLE,
        "initialized idle flow",
    )
