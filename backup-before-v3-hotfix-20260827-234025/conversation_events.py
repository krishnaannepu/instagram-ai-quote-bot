from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from enum import Enum
from typing import Any


class EventType(str, Enum):
    GREETING = "GREETING"

    START_QUOTE = "START_QUOTE"
    START_NEW_QUOTE = "START_NEW_QUOTE"

    FIELD_VALUE = "FIELD_VALUE"
    CHANGE_FIELD = "CHANGE_FIELD"

    PAUSE = "PAUSE"
    UNCLEAR = "UNCLEAR"

    BUSINESS_QUESTION = "BUSINESS_QUESTION"
    BUSINESS_QUESTION_RESOLVED = "BUSINESS_QUESTION_RESOLVED"

    PACKAGE_RECONSIDERATION_REQUEST = "PACKAGE_RECONSIDERATION_REQUEST"
    KEEP_CURRENT_PACKAGE = "KEEP_CURRENT_PACKAGE"
    SWITCH_PACKAGE = "SWITCH_PACKAGE"

    START_DEFERRED_REVIEW = "START_DEFERRED_REVIEW"

    QUOTE_COMPLETED = "QUOTE_COMPLETED"

    EMAIL_YES = "EMAIL_YES"
    EMAIL_NO = "EMAIL_NO"
    EMAIL_ADDRESS_VALUE = "EMAIL_ADDRESS_VALUE"
    INVALID_EMAIL = "INVALID_EMAIL"

    SPEAK_TO_TEAM = "SPEAK_TO_TEAM"
    REQUEST_CALLBACK = "REQUEST_CALLBACK"

    CALLBACK_PHONE_VALUE = "CALLBACK_PHONE_VALUE"
    INVALID_PHONE = "INVALID_PHONE"
    CALLBACK_PREFERENCE_VALUE = "CALLBACK_PREFERENCE_VALUE"

    FINISH = "FINISH"


@dataclass(frozen=True)
class ConversationEvent:
    type: EventType

    field: str | None = None
    value: Any = None

    question_type: str | None = None
    question_text: str | None = None

    metadata: dict[str, Any] = dataclass_field(
        default_factory=dict
    )
