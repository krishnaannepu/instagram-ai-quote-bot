from __future__ import annotations

from typing import Any

from conversation_events import ConversationEvent, EventType
from conversation_models import ConversationContext, FlowState
from semantic_contract import (
    SemanticAction,
    SemanticInterpretation,
    is_action_allowed,
)


class EventNormalizationError(ValueError):
    pass


BUTTON_FIELD_VALUES: dict[str, tuple[str, Any]] = {
    "SERVICE_WEDDING": ("service", "Wedding"),
    "SERVICE_BIRTHDAY": ("service", "Birthday"),
    "SERVICE_PORTRAIT": ("service", "Portrait"),
    "SERVICE_EVENT": ("service", "Event"),

    "PACKAGE_BASIC": ("package", "Basic"),
    "PACKAGE_PREMIUM": ("package", "Premium"),

    "COVERAGE_PHOTOGRAPHY": ("coverage_type", "Photography"),
    "COVERAGE_VIDEOGRAPHY": ("coverage_type", "Videography"),
    "COVERAGE_BOTH": ("coverage_type", "Both"),

    "TRAVEL_YES": ("travel_required", "Yes"),
    "TRAVEL_NO": ("travel_required", "No"),
}


BUTTON_DIRECT_EVENTS: dict[str, EventType] = {
    "GET_QUOTE": EventType.START_QUOTE,
    "START_NEW_QUOTE": EventType.START_NEW_QUOTE,
    "FINISH": EventType.FINISH,

    "EMAIL_YES": EventType.EMAIL_YES,
    "EMAIL_NO": EventType.EMAIL_NO,

    "SPEAK_TO_TEAM": EventType.SPEAK_TO_TEAM,
    "REQUEST_CALLBACK": EventType.REQUEST_CALLBACK,

    # V3 package reconfirmation buttons.
    "KEEP_CURRENT_PACKAGE": EventType.KEEP_CURRENT_PACKAGE,
}


BUTTON_SWITCH_PACKAGES: dict[str, str] = {
    "SWITCH_PACKAGE_BASIC": "Basic",
    "SWITCH_PACKAGE_PREMIUM": "Premium",
}


BUTTON_CALLBACK_PREFERENCES: dict[str, str] = {
    "CALLBACK_ASAP": "ASAP",
    "CALLBACK_MORNING": "Morning",
    "CALLBACK_AFTERNOON": "Afternoon",
}


class EventNormalizer:
    def from_button(
        self,
        context: ConversationContext,
        payload: str,
    ) -> ConversationEvent:
        normalized_payload = str(payload or "").strip().upper()

        if not normalized_payload:
            raise EventNormalizationError(
                "Button payload is empty."
            )

        if normalized_payload in BUTTON_CALLBACK_PREFERENCES:
            if context.state != FlowState.CALLBACK_PREFERENCE:
                raise EventNormalizationError(
                    "Callback preference button is only valid during "
                    "CALLBACK_PREFERENCE."
                )

            return ConversationEvent(
                type=EventType.CALLBACK_PREFERENCE_VALUE,
                value=BUTTON_CALLBACK_PREFERENCES[
                    normalized_payload
                ],
                metadata={
                    "source": "button",
                    "payload": normalized_payload,
                },
            )

        if normalized_payload in BUTTON_SWITCH_PACKAGES:
            if context.state != FlowState.PACKAGE_RECONFIRMATION:
                raise EventNormalizationError(
                    "Package switch button is only valid during "
                    "PACKAGE_RECONFIRMATION."
                )

            return ConversationEvent(
                type=EventType.SWITCH_PACKAGE,
                value=BUTTON_SWITCH_PACKAGES[
                    normalized_payload
                ],
                metadata={
                    "source": "button",
                    "payload": normalized_payload,
                },
            )

        if normalized_payload in BUTTON_DIRECT_EVENTS:
            event_type = BUTTON_DIRECT_EVENTS[
                normalized_payload
            ]

            if (
                event_type == EventType.KEEP_CURRENT_PACKAGE
                and context.state != FlowState.PACKAGE_RECONFIRMATION
            ):
                raise EventNormalizationError(
                    "Keep-package button is only valid during "
                    "PACKAGE_RECONFIRMATION."
                )

            event = ConversationEvent(
                type=event_type,
                metadata={
                    "source": "button",
                    "payload": normalized_payload,
                },
            )

            self._validate_button_event(
                context,
                event,
            )

            return event

        field_value = BUTTON_FIELD_VALUES.get(
            normalized_payload
        )

        if field_value is None:
            raise EventNormalizationError(
                f"Unknown V3 button payload: {normalized_payload}"
            )

        field_name, value = field_value

        event = ConversationEvent(
            type=EventType.FIELD_VALUE,
            field=field_name,
            value=value,
            metadata={
                "source": "button",
                "payload": normalized_payload,
            },
        )

        self._validate_field_event_for_state(
            context=context,
            event=event,
        )

        return event

    def from_semantic(
        self,
        context: ConversationContext,
        interpretation: SemanticInterpretation,
    ) -> ConversationEvent:
        if not is_action_allowed(
            context.state,
            interpretation.action,
        ):
            raise EventNormalizationError(
                f"Semantic action {interpretation.action.value} "
                f"is not allowed while state is {context.state.value}."
            )

        action = interpretation.action

        if action == SemanticAction.GREETING:
            return ConversationEvent(
                type=EventType.GREETING,
                metadata=self._semantic_metadata(
                    interpretation
                ),
            )

        if action == SemanticAction.FIELD_VALUE:
            event = ConversationEvent(
                type=EventType.FIELD_VALUE,
                field=interpretation.field_name,
                value=interpretation.value,
                metadata=self._semantic_metadata(
                    interpretation
                ),
            )

            self._validate_field_event_for_state(
                context=context,
                event=event,
            )

            return event

        if action == SemanticAction.CHANGE_FIELD:
            if not interpretation.field_name:
                raise EventNormalizationError(
                    "CHANGE_FIELD requires field_name."
                )

            if interpretation.value in {None, ""}:
                raise EventNormalizationError(
                    "CHANGE_FIELD requires value."
                )

            return ConversationEvent(
                type=EventType.CHANGE_FIELD,
                field=interpretation.field_name,
                value=interpretation.value,
                metadata=self._semantic_metadata(
                    interpretation
                ),
            )

        if action == SemanticAction.BUSINESS_QUESTION:
            if not interpretation.question_text:
                raise EventNormalizationError(
                    "BUSINESS_QUESTION requires question_text."
                )

            return ConversationEvent(
                type=EventType.BUSINESS_QUESTION,
                question_type=interpretation.question_type,
                question_text=interpretation.question_text,
                metadata=self._semantic_metadata(
                    interpretation
                ),
            )

        if action == SemanticAction.PACKAGE_RECONSIDERATION:
            if not context.quote.package:
                raise EventNormalizationError(
                    "PACKAGE_RECONSIDERATION requires "
                    "an existing selected package."
                )

            return ConversationEvent(
                type=EventType.PACKAGE_RECONSIDERATION_REQUEST,
                question_type=interpretation.question_type,
                question_text=interpretation.question_text,
                metadata=self._semantic_metadata(
                    interpretation
                ),
            )

        if action == SemanticAction.KEEP_CURRENT_PACKAGE:
            return ConversationEvent(
                type=EventType.KEEP_CURRENT_PACKAGE,
                metadata=self._semantic_metadata(
                    interpretation
                ),
            )

        if action == SemanticAction.SWITCH_PACKAGE:
            if not interpretation.value:
                raise EventNormalizationError(
                    "SWITCH_PACKAGE requires the target package."
                )

            return ConversationEvent(
                type=EventType.SWITCH_PACKAGE,
                value=interpretation.value,
                metadata=self._semantic_metadata(
                    interpretation
                ),
            )

        if action == SemanticAction.EMAIL_YES:
            return ConversationEvent(
                type=EventType.EMAIL_YES,
                metadata=self._semantic_metadata(
                    interpretation
                ),
            )

        if action == SemanticAction.EMAIL_NO:
            return ConversationEvent(
                type=EventType.EMAIL_NO,
                metadata=self._semantic_metadata(
                    interpretation
                ),
            )

        if action == SemanticAction.SPEAK_TO_TEAM:
            return ConversationEvent(
                type=EventType.SPEAK_TO_TEAM,
                metadata=self._semantic_metadata(
                    interpretation
                ),
            )

        if action == SemanticAction.REQUEST_CALLBACK:
            return ConversationEvent(
                type=EventType.REQUEST_CALLBACK,
                metadata=self._semantic_metadata(
                    interpretation
                ),
            )

        if action == SemanticAction.CALLBACK_PREFERENCE_VALUE:
            if interpretation.value not in {
                "ASAP",
                "Morning",
                "Afternoon",
            }:
                raise EventNormalizationError(
                    "CALLBACK_PREFERENCE_VALUE requires ASAP, Morning, "
                    "or Afternoon."
                )

            return ConversationEvent(
                type=EventType.CALLBACK_PREFERENCE_VALUE,
                value=interpretation.value,
                metadata=self._semantic_metadata(
                    interpretation
                ),
            )

        if action == SemanticAction.PAUSE:
            return ConversationEvent(
                type=EventType.PAUSE,
                metadata=self._semantic_metadata(
                    interpretation
                ),
            )

        if action == SemanticAction.UNCLEAR:
            return ConversationEvent(
                type=EventType.UNCLEAR,
                metadata=self._semantic_metadata(
                    interpretation
                ),
            )

        if action == SemanticAction.START_DEFERRED_REVIEW:
            return ConversationEvent(
                type=EventType.START_DEFERRED_REVIEW,
                metadata=self._semantic_metadata(
                    interpretation
                ),
            )

        if action == SemanticAction.START_NEW_QUOTE:
            return ConversationEvent(
                type=EventType.START_NEW_QUOTE,
                metadata=self._semantic_metadata(
                    interpretation
                ),
            )

        if action == SemanticAction.FINISH:
            return ConversationEvent(
                type=EventType.FINISH,
                metadata=self._semantic_metadata(
                    interpretation
                ),
            )

        raise EventNormalizationError(
            f"No event mapping for semantic action {action.value}."
        )

    def _validate_field_event_for_state(
        self,
        context: ConversationContext,
        event: ConversationEvent,
    ) -> None:
        expected_field = context.expected_field()

        if expected_field is None:
            raise EventNormalizationError(
                f"State {context.state.value} "
                f"is not expecting a quote field."
            )

        if event.field != expected_field:
            raise EventNormalizationError(
                f"State {context.state.value} expects "
                f"{expected_field!r}; received {event.field!r}."
            )

    def _validate_button_event(
        self,
        context: ConversationContext,
        event: ConversationEvent,
    ) -> None:
        if event.type == EventType.START_QUOTE:
            if context.state not in {
                FlowState.IDLE,
                FlowState.FINISHED,
                FlowState.POST_QUOTE,
                FlowState.QUOTE_READY,
            }:
                raise EventNormalizationError(
                    f"GET_QUOTE is not valid from "
                    f"{context.state.value}."
                )

        if event.type == EventType.EMAIL_YES:
            if context.state != FlowState.EMAIL_CONFIRMATION:
                raise EventNormalizationError(
                    "EMAIL_YES button is only valid during EMAIL_CONFIRMATION."
                )
            return

        if event.type == EventType.EMAIL_NO:
            if context.state != FlowState.EMAIL_CONFIRMATION:
                raise EventNormalizationError(
                    "EMAIL_NO button is only valid during EMAIL_CONFIRMATION."
                )
            return

        if event.type == EventType.FINISH:
            return

    def _semantic_metadata(
        self,
        interpretation: SemanticInterpretation,
    ) -> dict[str, Any]:
        metadata = dict(
            interpretation.metadata or {}
        )

        metadata.update(
            {
                "source": "semantic",
                "confidence": interpretation.confidence,
                "language": interpretation.language,
            }
        )

        return metadata
