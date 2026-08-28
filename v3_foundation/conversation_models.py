from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class FlowState(str, Enum):
    IDLE = "IDLE"

    QUOTE_SERVICE = "QUOTE_SERVICE"
    QUOTE_PACKAGE = "QUOTE_PACKAGE"
    QUOTE_COVERAGE = "QUOTE_COVERAGE"
    QUOTE_TRAVEL = "QUOTE_TRAVEL"
    QUOTE_DURATION = "QUOTE_DURATION"
    QUOTE_DATE = "QUOTE_DATE"
    QUOTE_LOCATION = "QUOTE_LOCATION"

    BUSINESS_INTERRUPT = "BUSINESS_INTERRUPT"
    PACKAGE_RECONFIRMATION = "PACKAGE_RECONFIRMATION"
    DEFERRED_REVIEW = "DEFERRED_REVIEW"

    QUOTE_READY = "QUOTE_READY"

    EMAIL_CONFIRMATION = "EMAIL_CONFIRMATION"
    EMAIL_ADDRESS = "EMAIL_ADDRESS"
    POST_QUOTE = "POST_QUOTE"
    HANDOFF_OPTIONS = "HANDOFF_OPTIONS"

    CALLBACK_PHONE = "CALLBACK_PHONE"
    CALLBACK_PREFERENCE = "CALLBACK_PREFERENCE"
    CALLBACK_RECORDED = "CALLBACK_RECORDED"

    FINISHED = "FINISHED"


QUOTE_STATE_TO_FIELD: dict[FlowState, str] = {
    FlowState.QUOTE_SERVICE: "service",
    FlowState.QUOTE_PACKAGE: "package",
    FlowState.QUOTE_COVERAGE: "coverage_type",
    FlowState.QUOTE_TRAVEL: "travel_required",
    FlowState.QUOTE_DURATION: "duration_hours",
    FlowState.QUOTE_DATE: "event_date",
    FlowState.QUOTE_LOCATION: "location",
}

FIELD_TO_QUOTE_STATE: dict[str, FlowState] = {
    field_name: state
    for state, field_name in QUOTE_STATE_TO_FIELD.items()
}

QUOTE_FIELD_ORDER: list[str] = [
    "service",
    "package",
    "coverage_type",
    "travel_required",
    "duration_hours",
    "event_date",
    "location",
]


@dataclass
class QuoteData:
    service: str | None = None
    package: str | None = None
    coverage_type: str | None = None
    travel_required: str | None = None
    duration_hours: float | int | None = None
    event_date: str | None = None
    location: str | None = None

    def get(self, field_name: str) -> Any:
        if field_name not in QUOTE_FIELD_ORDER:
            raise KeyError(f"Unknown quote field: {field_name}")
        return getattr(self, field_name)

    def set(self, field_name: str, value: Any) -> None:
        if field_name not in QUOTE_FIELD_ORDER:
            raise KeyError(f"Unknown quote field: {field_name}")
        setattr(self, field_name, value)

    def clear(self) -> None:
        for field_name in QUOTE_FIELD_ORDER:
            setattr(self, field_name, None)

    def as_dict(self) -> dict[str, Any]:
        return {
            field_name: getattr(self, field_name)
            for field_name in QUOTE_FIELD_ORDER
        }


@dataclass
class CustomerData:
    email: str = ""
    phone: str = ""
    callback_preference: str = ""


@dataclass
class QuoteLifecycleData:
    quote_data: dict[str, Any] = field(default_factory=dict)
    lead_data: dict[str, Any] = field(default_factory=dict)
    active_lead_id: str = ""

    quote_email_sent: bool = False
    quote_persisted: bool = False

    handoff_requested: bool = False
    handoff_requested_at: str = ""
    handoff_status: str = ""
    handoff_notification_sent: bool = False

    callback_request_sent: bool = False
    callback_notification_sent: bool = False


@dataclass
class TransitionRecord:
    from_state: FlowState
    event_type: str
    to_state: FlowState
    note: str = ""


@dataclass
class ConversationContext:
    state: FlowState = FlowState.IDLE
    quote: QuoteData = field(default_factory=QuoteData)
    customer: CustomerData = field(default_factory=CustomerData)
    lifecycle: QuoteLifecycleData = field(default_factory=QuoteLifecycleData)

    resume_stack: list[FlowState] = field(default_factory=list)
    deferred_fields: list[str] = field(default_factory=list)
    reviewing_deferred: bool = False

    current_package_before_reconfirmation: str | None = None

    quote_version: int = 0
    quote_is_stale: bool = False

    transition_log: list[TransitionRecord] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def expected_field(self) -> str | None:
        return QUOTE_STATE_TO_FIELD.get(self.state)

    def log_transition(
        self,
        from_state: FlowState,
        event_type: str,
        to_state: FlowState,
        note: str = "",
    ) -> None:
        self.transition_log.append(
            TransitionRecord(
                from_state=from_state,
                event_type=event_type,
                to_state=to_state,
                note=note,
            )
        )

    def reset_for_new_quote(self) -> None:
        self.quote.clear()
        self.customer = CustomerData()
        self.lifecycle = QuoteLifecycleData()

        self.resume_stack.clear()
        self.deferred_fields.clear()
        self.reviewing_deferred = False
        self.current_package_before_reconfirmation = None

        self.quote_version = 0
        self.quote_is_stale = False

        self.state = FlowState.QUOTE_SERVICE

    def push_resume_state(self, state: FlowState | None = None) -> None:
        resume_state = state or self.state

        if resume_state == FlowState.BUSINESS_INTERRUPT:
            raise ValueError(
                "BUSINESS_INTERRUPT cannot be pushed as a resume state."
            )

        self.resume_stack.append(resume_state)

    def pop_resume_state(self) -> FlowState | None:
        if not self.resume_stack:
            return None

        return self.resume_stack.pop()
