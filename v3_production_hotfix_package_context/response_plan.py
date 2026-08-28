from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from conversation_models import FlowState


class ResponseAction(str, Enum):
    WELCOME = "WELCOME"

    ASK_FIELD = "ASK_FIELD"
    RESUME_FIELD = "RESUME_FIELD"

    ANSWER_BUSINESS_QUESTION = "ANSWER_BUSINESS_QUESTION"
    ANSWER_PACKAGE_RECONSIDERATION = "ANSWER_PACKAGE_RECONSIDERATION"

    ASK_PACKAGE_RECONFIRMATION = "ASK_PACKAGE_RECONFIRMATION"
    WAIT_PACKAGE_RECONFIRMATION = "WAIT_PACKAGE_RECONFIRMATION"

    REVIEW_DEFERRED_FIELDS = "REVIEW_DEFERRED_FIELDS"

    QUOTE_READY = "QUOTE_READY"

    ASK_EMAIL_CONFIRMATION = "ASK_EMAIL_CONFIRMATION"
    ASK_EMAIL_ADDRESS = "ASK_EMAIL_ADDRESS"
    INVALID_EMAIL = "INVALID_EMAIL"
    SEND_QUOTE_EMAIL = "SEND_QUOTE_EMAIL"
    EMAIL_SENT = "EMAIL_SENT"
    EMAIL_FAILED = "EMAIL_FAILED"

    POST_QUOTE_OPTIONS = "POST_QUOTE_OPTIONS"

    PROCESS_HANDOFF_REQUEST = "PROCESS_HANDOFF_REQUEST"
    HANDOFF_OPTIONS = "HANDOFF_OPTIONS"

    START_CALLBACK_REQUEST = "START_CALLBACK_REQUEST"
    ASK_CALLBACK_PHONE = "ASK_CALLBACK_PHONE"
    INVALID_PHONE = "INVALID_PHONE"
    ASK_CALLBACK_PREFERENCE = "ASK_CALLBACK_PREFERENCE"
    PROCESS_CALLBACK_REQUEST = "PROCESS_CALLBACK_REQUEST"
    CALLBACK_RECORDED = "CALLBACK_RECORDED"
    CALLBACK_ALREADY_RECORDED = "CALLBACK_ALREADY_RECORDED"

    PAUSED = "PAUSED"
    CLARIFY = "CLARIFY"

    STARTED_NEW_QUOTE = "STARTED_NEW_QUOTE"
    FINISHED = "FINISHED"


@dataclass(frozen=True)
class ResponsePlan:
    action: ResponseAction
    state: FlowState

    next_field: str | None = None
    options: list[str] = field(default_factory=list)

    business_question_type: str | None = None
    business_question_text: str | None = None

    current_package: str | None = None

    deferred_fields: list[str] = field(default_factory=list)

    changed_fields: list[str] = field(default_factory=list)

    language: str = "English"

    metadata: dict[str, Any] = field(default_factory=dict)
