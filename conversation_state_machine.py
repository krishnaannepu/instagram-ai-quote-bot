from __future__ import annotations

from dataclasses import dataclass

from conversation_events import ConversationEvent, EventType
from conversation_models import (
    ConversationContext,
    FIELD_TO_QUOTE_STATE,
    FlowState,
    QUOTE_FIELD_ORDER,
    QUOTE_STATE_TO_FIELD,
)


class InvalidTransitionError(RuntimeError):
    pass


@dataclass
class TransitionResult:
    previous_state: FlowState
    state: FlowState
    event_type: EventType

    changed_fields: list[str]
    deferred_fields: list[str]

    resume_prompt_required: bool = False
    package_reconfirmation_required: bool = False

    note: str = ""


class ConversationStateMachine:
    def handle(
        self,
        context: ConversationContext,
        event: ConversationEvent,
    ) -> TransitionResult:
        previous_state = context.state

        if event.type == EventType.GREETING:
            if context.state != FlowState.IDLE:
                raise InvalidTransitionError(
                    "GREETING is only valid from IDLE."
                )

            return self._result(
                context,
                previous_state,
                event,
                [],
                note="Greeting received; remaining in IDLE.",
            )

        if event.type in {
            EventType.START_QUOTE,
            EventType.START_NEW_QUOTE,
        }:
            context.reset_for_new_quote()

            return self._result(
                context,
                previous_state,
                event,
                [],
                note="Started fresh quote.",
            )

        if event.type == EventType.FINISH:
            context.state = FlowState.FINISHED

            return self._result(
                context,
                previous_state,
                event,
                [],
                note="Conversation finished.",
            )

        if event.type == EventType.SPEAK_TO_TEAM:
            if context.lifecycle.callback_request_sent:
                context.state = FlowState.CALLBACK_RECORDED
                note = "Customer requested team after callback was already recorded."
            else:
                context.state = FlowState.HANDOFF_OPTIONS
                note = "Customer requested human handoff."

            return self._result(
                context,
                previous_state,
                event,
                [],
                note=note,
            )

        if event.type == EventType.REQUEST_CALLBACK:
            if context.lifecycle.callback_request_sent:
                context.state = FlowState.CALLBACK_RECORDED
                note = "Duplicate callback request; callback already recorded."
            else:
                context.state = FlowState.CALLBACK_PHONE
                note = "Started callback request; awaiting phone number."

            return self._result(
                context,
                previous_state,
                event,
                [],
                note=note,
            )

        if event.type == EventType.CALLBACK_PHONE_VALUE:
            if context.state != FlowState.CALLBACK_PHONE:
                raise InvalidTransitionError(
                    "CALLBACK_PHONE_VALUE requires CALLBACK_PHONE."
                )

            phone = str(
                event.value or ""
            ).strip()

            if not phone:
                raise InvalidTransitionError(
                    "CALLBACK_PHONE_VALUE requires a value."
                )

            context.customer.phone = phone
            context.state = FlowState.CALLBACK_PREFERENCE

            return self._result(
                context,
                previous_state,
                event,
                ["customer_phone"],
                note="Callback phone saved; awaiting callback preference.",
            )

        if event.type == EventType.INVALID_PHONE:
            if context.state != FlowState.CALLBACK_PHONE:
                raise InvalidTransitionError(
                    "INVALID_PHONE requires CALLBACK_PHONE."
                )

            return self._result(
                context,
                previous_state,
                event,
                [],
                note="Invalid callback phone; state unchanged.",
            )

        if event.type == EventType.CALLBACK_PREFERENCE_VALUE:
            if context.state != FlowState.CALLBACK_PREFERENCE:
                raise InvalidTransitionError(
                    "CALLBACK_PREFERENCE_VALUE requires CALLBACK_PREFERENCE."
                )

            preference = str(
                event.value or ""
            ).strip()

            if preference not in {
                "ASAP",
                "Morning",
                "Afternoon",
            }:
                raise InvalidTransitionError(
                    "Unsupported callback preference."
                )

            context.customer.callback_preference = preference
            context.state = FlowState.CALLBACK_RECORDED

            return self._result(
                context,
                previous_state,
                event,
                ["callback_preference"],
                note="Callback preference saved; callback ready to record.",
            )

        if event.type == EventType.QUOTE_COMPLETED:
            if context.state != FlowState.QUOTE_READY:
                raise InvalidTransitionError(
                    "QUOTE_COMPLETED requires QUOTE_READY."
                )

            context.state = FlowState.EMAIL_CONFIRMATION

            return self._result(
                context,
                previous_state,
                event,
                [],
                note="Quote completed; awaiting email decision.",
            )

        if event.type == EventType.EMAIL_YES:
            if context.state != FlowState.EMAIL_CONFIRMATION:
                raise InvalidTransitionError(
                    "EMAIL_YES requires EMAIL_CONFIRMATION."
                )

            context.state = FlowState.EMAIL_ADDRESS

            return self._result(
                context,
                previous_state,
                event,
                [],
                note="Customer requested quote email.",
            )

        if event.type == EventType.EMAIL_NO:
            if context.state != FlowState.EMAIL_CONFIRMATION:
                raise InvalidTransitionError(
                    "EMAIL_NO requires EMAIL_CONFIRMATION."
                )

            context.state = FlowState.POST_QUOTE

            return self._result(
                context,
                previous_state,
                event,
                [],
                note="Customer declined quote email.",
            )

        if event.type == EventType.EMAIL_ADDRESS_VALUE:
            if context.state != FlowState.EMAIL_ADDRESS:
                raise InvalidTransitionError(
                    "EMAIL_ADDRESS_VALUE requires EMAIL_ADDRESS."
                )

            email = str(
                event.value or ""
            ).strip().lower()

            if not email:
                raise InvalidTransitionError(
                    "EMAIL_ADDRESS_VALUE requires a value."
                )

            context.customer.email = email
            context.state = FlowState.POST_QUOTE

            return self._result(
                context,
                previous_state,
                event,
                ["customer_email"],
                note="Customer email saved.",
            )

        if event.type == EventType.INVALID_EMAIL:
            if context.state != FlowState.EMAIL_ADDRESS:
                raise InvalidTransitionError(
                    "INVALID_EMAIL requires EMAIL_ADDRESS."
                )

            return self._result(
                context,
                previous_state,
                event,
                [],
                note="Invalid customer email; state unchanged.",
            )

        if event.type == EventType.INVALID_FIELD_VALUE:
            return self._result(
                context,
                previous_state,
                event,
                [],
                note="Rejected value outside Python-approved domain; state unchanged.",
            )

        if event.type == EventType.BUSINESS_QUESTION:
            return self._start_business_interrupt(
                context,
                event,
                previous_state,
            )

        if event.type == EventType.BUSINESS_QUESTION_RESOLVED:
            return self._resolve_business_interrupt(
                context,
                event,
                previous_state,
            )

        if event.type == EventType.PACKAGE_RECONSIDERATION_REQUEST:
            return self._start_package_reconfirmation(
                context,
                event,
                previous_state,
            )

        if event.type in {
            EventType.KEEP_CURRENT_PACKAGE,
            EventType.SWITCH_PACKAGE,
        }:
            return self._resolve_package_reconfirmation(
                context,
                event,
                previous_state,
            )

        if event.type == EventType.START_DEFERRED_REVIEW:
            return self._start_deferred_review(
                context,
                event,
                previous_state,
            )

        if event.type == EventType.STATUS_QUESTION:
            # A question about the current quote is read-only. Answering it
            # must never move the conversation or reopen a decision.
            return self._result(
                context,
                previous_state,
                event,
                [],
                note=(
                    "Answered a question about current quote state; "
                    "state unchanged."
                ),
            )

        if event.type == EventType.PAUSE:
            return self._result(
                context,
                previous_state,
                event,
                [],
                note="Customer paused; state unchanged.",
            )

        if event.type == EventType.UNCLEAR:
            return self._defer_current_field(
                context,
                event,
                previous_state,
            )

        if event.type == EventType.FIELD_VALUE:
            changed = self._apply_expected_field_value(
                context,
                event,
            )

            return self._result(
                context,
                previous_state,
                event,
                changed,
                note="Applied expected quote field.",
            )

        if event.type == EventType.CHANGE_FIELD:
            expected_before = context.expected_field()

            changed = self._apply_change_field(
                context,
                event,
            )

            # Answering the field the flow is currently waiting on has to move
            # the conversation forward, whether the customer phrased it as an
            # answer or as a correction. Otherwise the bot asks again for the
            # thing it was just told.
            if event.field == expected_before:
                if context.reviewing_deferred:
                    self._advance_deferred_review(
                        context
                    )
                else:
                    self._advance_standard_quote(
                        context
                    )

            return self._result(
                context,
                previous_state,
                event,
                changed,
                note="Changed known quote field.",
            )

        raise InvalidTransitionError(
            f"Unsupported event type: {event.type}"
        )

    # ------------------------------------------------------------------
    # Quote progression
    # ------------------------------------------------------------------

    def _apply_expected_field_value(
        self,
        context: ConversationContext,
        event: ConversationEvent,
    ) -> list[str]:
        expected_field = context.expected_field()

        if expected_field is None:
            raise InvalidTransitionError(
                f"{context.state} is not expecting a quote value."
            )

        if event.field != expected_field:
            raise InvalidTransitionError(
                f"{context.state} expects {expected_field!r}, "
                f"received {event.field!r}."
            )

        if event.value is None or event.value == "":
            raise InvalidTransitionError(
                f"Empty value for {event.field!r}."
            )

        old_value = context.quote.get(
            event.field
        )

        context.quote.set(
            event.field,
            event.value,
        )

        changed_fields: list[str] = []

        if old_value != event.value:
            changed_fields.append(
                event.field
            )

            if context.quote_version > 0:
                self._mark_quote_stale(
                    context
                )

        if event.field in context.deferred_fields:
            context.deferred_fields.remove(
                event.field
            )

        if context.reviewing_deferred:
            self._advance_deferred_review(
                context
            )
        else:
            self._advance_standard_quote(
                context
            )

        return changed_fields

    def _advance_standard_quote(
        self,
        context: ConversationContext,
    ) -> None:
        current_field = QUOTE_STATE_TO_FIELD.get(
            context.state
        )

        if current_field is None:
            raise InvalidTransitionError(
                f"Cannot advance state {context.state}."
            )

        current_index = QUOTE_FIELD_ORDER.index(
            current_field
        )

        for next_field in QUOTE_FIELD_ORDER[
            current_index + 1:
        ]:
            if context.quote.get(
                next_field
            ) is None:
                context.state = FIELD_TO_QUOTE_STATE[
                    next_field
                ]
                return

        if context.deferred_fields:
            context.state = FlowState.DEFERRED_REVIEW
        else:
            context.state = FlowState.QUOTE_READY

    def _defer_current_field(
        self,
        context: ConversationContext,
        event: ConversationEvent,
        previous_state: FlowState,
    ) -> TransitionResult:
        field_name = context.expected_field()

        if field_name is None:
            raise InvalidTransitionError(
                "UNCLEAR can only defer an expected quote field."
            )

        if field_name not in context.deferred_fields:
            context.deferred_fields.append(
                field_name
            )

        if context.reviewing_deferred:
            self._advance_deferred_review(
                context
            )
        else:
            self._advance_standard_quote(
                context
            )

        return self._result(
            context,
            previous_state,
            event,
            [],
            note=f"Deferred unresolved field {field_name}.",
        )

    # ------------------------------------------------------------------
    # Deferred review
    # ------------------------------------------------------------------

    def _start_deferred_review(
        self,
        context: ConversationContext,
        event: ConversationEvent,
        previous_state: FlowState,
    ) -> TransitionResult:
        if context.state != FlowState.DEFERRED_REVIEW:
            raise InvalidTransitionError(
                "Deferred review can only start from DEFERRED_REVIEW."
            )

        if not context.deferred_fields:
            context.state = FlowState.QUOTE_READY

            return self._result(
                context,
                previous_state,
                event,
                [],
                note="No deferred fields remain.",
            )

        context.reviewing_deferred = True

        next_field = context.deferred_fields[0]
        context.state = FIELD_TO_QUOTE_STATE[
            next_field
        ]

        return self._result(
            context,
            previous_state,
            event,
            [],
            note=f"Reviewing deferred field {next_field}.",
        )

    def _advance_deferred_review(
        self,
        context: ConversationContext,
    ) -> None:
        if context.deferred_fields:
            next_field = context.deferred_fields[0]
            context.state = FIELD_TO_QUOTE_STATE[
                next_field
            ]
            return

        context.reviewing_deferred = False
        context.state = FlowState.QUOTE_READY

    # ------------------------------------------------------------------
    # Business question interrupt
    # ------------------------------------------------------------------

    def _start_business_interrupt(
        self,
        context: ConversationContext,
        event: ConversationEvent,
        previous_state: FlowState,
    ) -> TransitionResult:
        if context.state == FlowState.BUSINESS_INTERRUPT:
            raise InvalidTransitionError(
                "Already inside BUSINESS_INTERRUPT."
            )

        context.push_resume_state()
        context.state = FlowState.BUSINESS_INTERRUPT

        context.metadata[
            "active_business_question"
        ] = {
            "question_type":
                event.question_type,
            "question_text":
                event.question_text,
        }

        return self._result(
            context,
            previous_state,
            event,
            [],
            note="Started business-question interrupt.",
        )

    def _resolve_business_interrupt(
        self,
        context: ConversationContext,
        event: ConversationEvent,
        previous_state: FlowState,
    ) -> TransitionResult:
        if context.state != FlowState.BUSINESS_INTERRUPT:
            raise InvalidTransitionError(
                "BUSINESS_QUESTION_RESOLVED requires BUSINESS_INTERRUPT."
            )

        resume_state = context.pop_resume_state()

        if resume_state is None:
            raise InvalidTransitionError(
                "Business interrupt has no resume state."
            )

        context.metadata.pop(
            "active_business_question",
            None,
        )

        context.state = resume_state

        return self._result(
            context,
            previous_state,
            event,
            [],
            resume_prompt_required=True,
            note=f"Resumed {resume_state}.",
        )

    # ------------------------------------------------------------------
    # Package reconsideration
    # ------------------------------------------------------------------

    def _start_package_reconfirmation(
        self,
        context: ConversationContext,
        event: ConversationEvent,
        previous_state: FlowState,
    ) -> TransitionResult:
        current_package = context.quote.package

        if not current_package:
            raise InvalidTransitionError(
                "Cannot reconfirm before package selection."
            )

        if context.state == FlowState.PACKAGE_RECONFIRMATION:
            return self._result(
                context,
                previous_state,
                event,
                [],
                package_reconfirmation_required=True,
                note="Package reconfirmation already pending.",
            )

        context.push_resume_state()
        context.current_package_before_reconfirmation = (
            current_package
        )
        context.state = FlowState.PACKAGE_RECONFIRMATION

        return self._result(
            context,
            previous_state,
            event,
            [],
            package_reconfirmation_required=True,
            note=f"Reconfirming selected package {current_package}.",
        )

    def _resolve_package_reconfirmation(
        self,
        context: ConversationContext,
        event: ConversationEvent,
        previous_state: FlowState,
    ) -> TransitionResult:
        if context.state != FlowState.PACKAGE_RECONFIRMATION:
            raise InvalidTransitionError(
                f"{event.type} requires PACKAGE_RECONFIRMATION."
            )

        current_package = (
            context.current_package_before_reconfirmation
            or context.quote.package
        )

        changed_fields: list[str] = []

        if event.type == EventType.KEEP_CURRENT_PACKAGE:
            if not current_package:
                raise InvalidTransitionError(
                    "No package exists to keep."
                )

            context.quote.package = (
                current_package
            )

        else:
            if not event.value:
                raise InvalidTransitionError(
                    "SWITCH_PACKAGE requires a value."
                )

            old_package = context.quote.package
            context.quote.package = event.value

            if old_package != event.value:
                changed_fields.append(
                    "package"
                )

                if context.quote_version > 0:
                    self._mark_quote_stale(
                        context
                    )

        resume_state = context.pop_resume_state()

        if resume_state is None:
            raise InvalidTransitionError(
                "Package reconfirmation has no resume state."
            )

        context.current_package_before_reconfirmation = None

        if (
            changed_fields
            and context.quote_is_stale
            and resume_state
            in {
                FlowState.QUOTE_READY,
                FlowState.EMAIL_CONFIRMATION,
                FlowState.EMAIL_ADDRESS,
                FlowState.POST_QUOTE,
            }
        ):
            context.state = FlowState.QUOTE_READY
        else:
            context.state = resume_state

        return self._result(
            context,
            previous_state,
            event,
            changed_fields,
            resume_prompt_required=True,
            note=f"Package decision resolved; resumed {context.state}.",
        )

    # ------------------------------------------------------------------
    # Quote changes
    # ------------------------------------------------------------------

    def _apply_change_field(
        self,
        context: ConversationContext,
        event: ConversationEvent,
    ) -> list[str]:
        if event.field not in QUOTE_FIELD_ORDER:
            raise InvalidTransitionError(
                f"Unknown quote field {event.field!r}."
            )

        if event.value is None or event.value == "":
            raise InvalidTransitionError(
                "CHANGE_FIELD requires a value."
            )

        old_value = context.quote.get(
            event.field
        )

        context.quote.set(
            event.field,
            event.value,
        )

        if old_value == event.value:
            return []

        if context.quote_version > 0:
            self._mark_quote_stale(
                context
            )

            if context.state in {
                FlowState.QUOTE_READY,
                FlowState.EMAIL_CONFIRMATION,
                FlowState.EMAIL_ADDRESS,
                FlowState.POST_QUOTE,
            }:
                context.state = FlowState.QUOTE_READY

        return [
            event.field
        ]

    def _mark_quote_stale(
        self,
        context: ConversationContext,
    ) -> None:
        context.quote_is_stale = True
        context.lifecycle.quote_data = {}
        context.lifecycle.quote_email_sent = False
        context.lifecycle.quote_persisted = False

    # ------------------------------------------------------------------
    # Result/log helper
    # ------------------------------------------------------------------

    def _result(
        self,
        context: ConversationContext,
        previous_state: FlowState,
        event: ConversationEvent,
        changed_fields: list[str],
        resume_prompt_required: bool = False,
        package_reconfirmation_required: bool = False,
        note: str = "",
    ) -> TransitionResult:
        context.log_transition(
            previous_state,
            event.type.value,
            context.state,
            note,
        )

        return TransitionResult(
            previous_state=previous_state,
            state=context.state,
            event_type=event.type,
            changed_fields=changed_fields,
            deferred_fields=list(
                context.deferred_fields
            ),
            resume_prompt_required=
                resume_prompt_required,
            package_reconfirmation_required=
                package_reconfirmation_required,
            note=note,
        )
