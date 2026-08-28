from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from enum import Enum
from typing import Any

from conversation_models import FlowState


class SemanticAction(str, Enum):
    GREETING = "GREETING"

    FIELD_VALUE = "FIELD_VALUE"
    CHANGE_FIELD = "CHANGE_FIELD"

    BUSINESS_QUESTION = "BUSINESS_QUESTION"
    STATUS_QUESTION = "STATUS_QUESTION"

    PACKAGE_RECONSIDERATION = "PACKAGE_RECONSIDERATION"
    KEEP_CURRENT_PACKAGE = "KEEP_CURRENT_PACKAGE"
    SWITCH_PACKAGE = "SWITCH_PACKAGE"

    EMAIL_YES = "EMAIL_YES"
    EMAIL_NO = "EMAIL_NO"

    SPEAK_TO_TEAM = "SPEAK_TO_TEAM"
    REQUEST_CALLBACK = "REQUEST_CALLBACK"
    CALLBACK_PREFERENCE_VALUE = "CALLBACK_PREFERENCE_VALUE"

    PAUSE = "PAUSE"
    UNCLEAR = "UNCLEAR"

    START_DEFERRED_REVIEW = "START_DEFERRED_REVIEW"

    START_NEW_QUOTE = "START_NEW_QUOTE"
    FINISH = "FINISH"


@dataclass(frozen=True)
class SemanticInterpretation:
    action: SemanticAction

    field_name: str | None = None
    value: Any = None

    question_type: str | None = None
    question_text: str | None = None

    confidence: float | None = None
    language: str | None = None

    metadata: dict[str, Any] = dataclass_field(
        default_factory=dict
    )


QUOTE_FIELD_ACTIONS = {
    SemanticAction.FIELD_VALUE,
    SemanticAction.CHANGE_FIELD,
    SemanticAction.BUSINESS_QUESTION,
    SemanticAction.STATUS_QUESTION,
    SemanticAction.PACKAGE_RECONSIDERATION,
    SemanticAction.SPEAK_TO_TEAM,
    SemanticAction.REQUEST_CALLBACK,
    SemanticAction.PAUSE,
    SemanticAction.UNCLEAR,
    SemanticAction.FINISH,
}


STATE_ALLOWED_ACTIONS: dict[FlowState, set[SemanticAction]] = {
    FlowState.IDLE: {
        SemanticAction.GREETING,
        SemanticAction.START_NEW_QUOTE,
        SemanticAction.BUSINESS_QUESTION,
        SemanticAction.SPEAK_TO_TEAM,
        SemanticAction.REQUEST_CALLBACK,
        SemanticAction.FINISH,
    },

    FlowState.QUOTE_SERVICE: {
        SemanticAction.FIELD_VALUE,
        SemanticAction.STATUS_QUESTION,
        SemanticAction.BUSINESS_QUESTION,
        SemanticAction.SPEAK_TO_TEAM,
        SemanticAction.REQUEST_CALLBACK,
        SemanticAction.PAUSE,
        SemanticAction.UNCLEAR,
        SemanticAction.FINISH,
    },

    FlowState.QUOTE_PACKAGE: {
        SemanticAction.FIELD_VALUE,
        SemanticAction.STATUS_QUESTION,
        SemanticAction.BUSINESS_QUESTION,
        SemanticAction.SPEAK_TO_TEAM,
        SemanticAction.REQUEST_CALLBACK,
        SemanticAction.PAUSE,
        SemanticAction.UNCLEAR,
        SemanticAction.FINISH,
    },

    FlowState.QUOTE_COVERAGE: set(
        QUOTE_FIELD_ACTIONS
    ),

    FlowState.QUOTE_TRAVEL: set(
        QUOTE_FIELD_ACTIONS
    ),

    FlowState.QUOTE_DURATION: set(
        QUOTE_FIELD_ACTIONS
    ),

    FlowState.QUOTE_DATE: set(
        QUOTE_FIELD_ACTIONS
    ),

    FlowState.QUOTE_LOCATION: set(
        QUOTE_FIELD_ACTIONS
    ),

    FlowState.BUSINESS_INTERRUPT:
        set(),

    FlowState.PACKAGE_RECONFIRMATION: {
        SemanticAction.KEEP_CURRENT_PACKAGE,
        SemanticAction.STATUS_QUESTION,
        SemanticAction.SWITCH_PACKAGE,
        SemanticAction.BUSINESS_QUESTION,
        SemanticAction.SPEAK_TO_TEAM,
        SemanticAction.REQUEST_CALLBACK,
        SemanticAction.PAUSE,
        SemanticAction.UNCLEAR,
        SemanticAction.FINISH,
    },

    FlowState.DEFERRED_REVIEW: {
        SemanticAction.START_DEFERRED_REVIEW,
        SemanticAction.BUSINESS_QUESTION,
        SemanticAction.SPEAK_TO_TEAM,
        SemanticAction.REQUEST_CALLBACK,
        SemanticAction.PAUSE,
        SemanticAction.FINISH,
    },

    FlowState.QUOTE_READY: {
        SemanticAction.CHANGE_FIELD,
        SemanticAction.STATUS_QUESTION,
        SemanticAction.BUSINESS_QUESTION,
        SemanticAction.PACKAGE_RECONSIDERATION,
        SemanticAction.SPEAK_TO_TEAM,
        SemanticAction.REQUEST_CALLBACK,
        SemanticAction.START_NEW_QUOTE,
        SemanticAction.FINISH,
    },

    FlowState.EMAIL_CONFIRMATION: {
        SemanticAction.EMAIL_YES,
        SemanticAction.EMAIL_NO,
        SemanticAction.BUSINESS_QUESTION,
        SemanticAction.PACKAGE_RECONSIDERATION,
        SemanticAction.CHANGE_FIELD,
        SemanticAction.SPEAK_TO_TEAM,
        SemanticAction.REQUEST_CALLBACK,
        SemanticAction.PAUSE,
        SemanticAction.FINISH,
    },

    # EMAIL_ADDRESS is interpreted deterministically by Python.
    # The semantic interpreter is not used for normal email-address input.
    FlowState.EMAIL_ADDRESS: {
        SemanticAction.BUSINESS_QUESTION,
        SemanticAction.PACKAGE_RECONSIDERATION,
        SemanticAction.CHANGE_FIELD,
        SemanticAction.SPEAK_TO_TEAM,
        SemanticAction.REQUEST_CALLBACK,
        SemanticAction.PAUSE,
        SemanticAction.FINISH,
    },

    FlowState.POST_QUOTE: {
        SemanticAction.CHANGE_FIELD,
        SemanticAction.STATUS_QUESTION,
        SemanticAction.BUSINESS_QUESTION,
        SemanticAction.PACKAGE_RECONSIDERATION,
        SemanticAction.SPEAK_TO_TEAM,
        SemanticAction.REQUEST_CALLBACK,
        SemanticAction.START_NEW_QUOTE,
        SemanticAction.FINISH,
    },

    FlowState.HANDOFF_OPTIONS: {
        SemanticAction.BUSINESS_QUESTION,
        SemanticAction.SPEAK_TO_TEAM,
        SemanticAction.REQUEST_CALLBACK,
        SemanticAction.START_NEW_QUOTE,
        SemanticAction.FINISH,
    },

    FlowState.CALLBACK_PHONE: {
        SemanticAction.BUSINESS_QUESTION,
        SemanticAction.PAUSE,
        SemanticAction.FINISH,
    },

    FlowState.CALLBACK_PREFERENCE: {
        SemanticAction.CALLBACK_PREFERENCE_VALUE,
        SemanticAction.BUSINESS_QUESTION,
        SemanticAction.PAUSE,
        SemanticAction.FINISH,
    },

    FlowState.CALLBACK_RECORDED: {
        SemanticAction.BUSINESS_QUESTION,
        SemanticAction.SPEAK_TO_TEAM,
        SemanticAction.REQUEST_CALLBACK,
        SemanticAction.START_NEW_QUOTE,
        SemanticAction.FINISH,
    },

    FlowState.FINISHED: {
        SemanticAction.START_NEW_QUOTE,
    },
}


def is_action_allowed(
    state: FlowState,
    action: SemanticAction,
) -> bool:
    return action in STATE_ALLOWED_ACTIONS.get(
        state,
        set(),
    )
