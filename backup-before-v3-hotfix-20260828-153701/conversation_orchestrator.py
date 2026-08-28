from __future__ import annotations

import re
from copy import deepcopy
from dataclasses import dataclass, replace
from typing import Protocol

from conversation_events import ConversationEvent, EventType
from conversation_models import ConversationContext, FlowState
from conversation_state_machine import (
    ConversationStateMachine,
    TransitionResult,
)
from event_normalizer import EventNormalizer
from response_plan import ResponseAction, ResponsePlan
from semantic_contract import SemanticAction, SemanticInterpretation
from turn_logger import build_turn_log


class SemanticInterpreter(Protocol):
    def interpret(
        self,
        context: ConversationContext,
        message_text: str,
        *,
        allowed_values: list[str] | None = None,
        supported_services: list[str] | None = None,
        packages_for_service: list[str] | None = None,
    ) -> SemanticInterpretation:
        ...


@dataclass
class OrchestratorResult:
    context: ConversationContext
    interpretation: SemanticInterpretation | None
    event: ConversationEvent
    response_plan: ResponsePlan
    turn_log: dict


class ConversationOrchestrator:
    EMAIL_PATTERN = re.compile(
        r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
    )

    def __init__(
        self,
        *,
        semantic_interpreter: SemanticInterpreter,
        state_machine: ConversationStateMachine | None = None,
        event_normalizer: EventNormalizer | None = None,
        supported_services: list[str] | None = None,
        packages_by_service: dict[str, list[str]] | None = None,
    ):
        self.semantic_interpreter = semantic_interpreter
        self.state_machine = state_machine or ConversationStateMachine()
        self.event_normalizer = event_normalizer or EventNormalizer()

        self.supported_services = list(
            supported_services
            or [
                "Wedding",
                "Birthday",
                "Portrait",
                "Event",
            ]
        )

        self.packages_by_service = dict(
            packages_by_service
            or {
                service: [
                    "Basic",
                    "Premium",
                ]
                for service in self.supported_services
            }
        )

    # ------------------------------------------------------------------
    # Public text entry
    # ------------------------------------------------------------------

    def handle_text(
        self,
        *,
        context: ConversationContext,
        message_text: str,
    ) -> OrchestratorResult:
        # Phone number itself is deterministic data, not an LLM decision.
        if context.state == FlowState.CALLBACK_PHONE:
            deterministic_phone = self._try_callback_phone_input(
                context=context,
                message_text=message_text,
            )

            if deterministic_phone is not None:
                return deterministic_phone

        # Email address itself is deterministic data, not an LLM decision.
        if context.state == FlowState.EMAIL_ADDRESS:
            deterministic = self._try_email_address_input(
                context=context,
                message_text=message_text,
            )

            if deterministic is not None:
                return deterministic

        before = deepcopy(
            context
        )

        interpretation = None
        event = None
        response_plan = None

        try:
            interpretation = (
                self.semantic_interpreter.interpret(
                    context=context,
                    message_text=message_text,
                    allowed_values=self._allowed_values(
                        context
                    ),
                    supported_services=self.supported_services,
                    packages_for_service=
                        self._packages_for_current_service(
                            context
                        ),
                )
            )

            interpretation, guarded_event = self._guard_catalogue_value(
                context=context,
                interpretation=interpretation,
            )

            if guarded_event is not None:
                event = guarded_event
            else:
                event = self.event_normalizer.from_semantic(
                    context=context,
                    interpretation=interpretation,
                )

            transition = self.state_machine.handle(
                context,
                event,
            )

            response_plan = self._plan_response(
                context=context,
                interpretation=interpretation,
                event=event,
                transition=transition,
            )

            turn_log = build_turn_log(
                context_before=before,
                context_after=context,
                customer_message=message_text,
                interpretation=interpretation,
                event=event,
                response_plan=response_plan,
            )

            return OrchestratorResult(
                context=context,
                interpretation=interpretation,
                event=event,
                response_plan=response_plan,
                turn_log=turn_log,
            )

        except Exception as error:
            turn_log = build_turn_log(
                context_before=before,
                context_after=context,
                customer_message=message_text,
                interpretation=interpretation,
                event=event,
                response_plan=response_plan,
                error=str(error),
            )

            raise ConversationOrchestratorError(
                str(error),
                turn_log=turn_log,
            ) from error

    # ------------------------------------------------------------------
    # Python catalogue/domain guard
    # ------------------------------------------------------------------

    def _guard_catalogue_value(
        self,
        *,
        context: ConversationContext,
        interpretation: SemanticInterpretation,
    ) -> tuple[SemanticInterpretation, ConversationEvent | None]:
        """Gemini interprets meaning; Python validates business values."""

        if interpretation.action == SemanticAction.FIELD_VALUE:
            allowed_values = self._allowed_values(context)

            if allowed_values:
                canonical = self._canonical_allowed_value(
                    interpretation.value,
                    allowed_values,
                )

                if canonical is None:
                    return (
                        interpretation,
                        ConversationEvent(
                            type=EventType.INVALID_FIELD_VALUE,
                            field=context.expected_field(),
                            value=interpretation.value,
                            metadata={
                                "source": "python_catalogue_guard",
                                "allowed_values": list(allowed_values),
                            },
                        ),
                    )

                if canonical != interpretation.value:
                    interpretation = replace(
                        interpretation,
                        value=canonical,
                    )

        if interpretation.action == SemanticAction.SWITCH_PACKAGE:
            allowed_packages = self._packages_for_current_service(context)
            canonical = self._canonical_allowed_value(
                interpretation.value,
                allowed_packages,
            )

            if canonical is None:
                return (
                    interpretation,
                    ConversationEvent(
                        type=EventType.INVALID_FIELD_VALUE,
                        field="package",
                        value=interpretation.value,
                        metadata={
                            "source": "python_catalogue_guard",
                            "allowed_values": list(allowed_packages),
                        },
                    ),
                )

            if canonical != interpretation.value:
                interpretation = replace(
                    interpretation,
                    value=canonical,
                )

        return interpretation, None

    def _canonical_allowed_value(
        self,
        value,
        allowed_values: list[str],
    ) -> str | None:
        normalized = str(value if value is not None else "").strip().casefold()

        if not normalized:
            return None

        for allowed in allowed_values:
            if str(allowed).strip().casefold() == normalized:
                return str(allowed)

        return None

    # ------------------------------------------------------------------
    # Public button entry
    # ------------------------------------------------------------------

    def handle_button(
        self,
        *,
        context: ConversationContext,
        payload: str,
    ) -> OrchestratorResult:
        before = deepcopy(
            context
        )

        event = None
        response_plan = None

        try:
            event = self.event_normalizer.from_button(
                context=context,
                payload=payload,
            )

            transition = self.state_machine.handle(
                context,
                event,
            )

            response_plan = self._plan_response(
                context=context,
                interpretation=None,
                event=event,
                transition=transition,
            )

            turn_log = build_turn_log(
                context_before=before,
                context_after=context,
                customer_message=f"[BUTTON:{payload}]",
                interpretation=None,
                event=event,
                response_plan=response_plan,
            )

            return OrchestratorResult(
                context=context,
                interpretation=None,
                event=event,
                response_plan=response_plan,
                turn_log=turn_log,
            )

        except Exception as error:
            turn_log = build_turn_log(
                context_before=before,
                context_after=context,
                customer_message=f"[BUTTON:{payload}]",
                interpretation=None,
                event=event,
                response_plan=response_plan,
                error=str(error),
            )

            raise ConversationOrchestratorError(
                str(error),
                turn_log=turn_log,
            ) from error

    # ------------------------------------------------------------------
    # Deterministic callback phone
    # ------------------------------------------------------------------

    def _try_callback_phone_input(
        self,
        *,
        context: ConversationContext,
        message_text: str,
    ) -> OrchestratorResult | None:
        stripped = str(
            message_text or ""
        ).strip()

        digits = re.sub(
            r"\D",
            "",
            stripped,
        )

        # If there are no digits, let the semantic layer decide whether this
        # is a side question or pause rather than pretending it is a phone.
        if not digits:
            return None

        before = deepcopy(
            context
        )

        if 7 <= len(digits) <= 15:
            event = ConversationEvent(
                type=EventType.CALLBACK_PHONE_VALUE,
                value=stripped,
                metadata={
                    "source": "deterministic_phone_parser",
                },
            )
        else:
            event = ConversationEvent(
                type=EventType.INVALID_PHONE,
                value=stripped,
                metadata={
                    "source": "deterministic_phone_parser",
                },
            )

        transition = self.state_machine.handle(
            context,
            event,
        )

        response_plan = self._plan_response(
            context=context,
            interpretation=None,
            event=event,
            transition=transition,
        )

        turn_log = build_turn_log(
            context_before=before,
            context_after=context,
            customer_message=message_text,
            interpretation=None,
            event=event,
            response_plan=response_plan,
        )

        return OrchestratorResult(
            context=context,
            interpretation=None,
            event=event,
            response_plan=response_plan,
            turn_log=turn_log,
        )

    # ------------------------------------------------------------------
    # Deterministic email address
    # ------------------------------------------------------------------

    def _try_email_address_input(
        self,
        *,
        context: ConversationContext,
        message_text: str,
    ) -> OrchestratorResult | None:
        stripped = str(
            message_text or ""
        ).strip()

        # A string containing @ is clearly attempting to provide an email,
        # even if the address is malformed. Keep it out of Gemini.
        contains_at = "@" in stripped

        match = self.EMAIL_PATTERN.search(
            stripped
        )

        if not match and not contains_at:
            # Could be a side business question such as "any discounts?"
            return None

        before = deepcopy(
            context
        )

        if match:
            event = ConversationEvent(
                type=EventType.EMAIL_ADDRESS_VALUE,
                value=match.group(0).lower(),
                metadata={
                    "source": "deterministic_email_parser",
                },
            )
        else:
            event = ConversationEvent(
                type=EventType.INVALID_EMAIL,
                value=stripped,
                metadata={
                    "source": "deterministic_email_parser",
                },
            )

        transition = self.state_machine.handle(
            context,
            event,
        )

        response_plan = self._plan_response(
            context=context,
            interpretation=None,
            event=event,
            transition=transition,
        )

        turn_log = build_turn_log(
            context_before=before,
            context_after=context,
            customer_message=message_text,
            interpretation=None,
            event=event,
            response_plan=response_plan,
        )

        return OrchestratorResult(
            context=context,
            interpretation=None,
            event=event,
            response_plan=response_plan,
            turn_log=turn_log,
        )

    # ------------------------------------------------------------------
    # Response planning
    # ------------------------------------------------------------------

    def _plan_response(
        self,
        *,
        context: ConversationContext,
        interpretation: SemanticInterpretation | None,
        event: ConversationEvent,
        transition: TransitionResult,
    ) -> ResponsePlan:
        language = (
            interpretation.language
            if interpretation
            and interpretation.language
            else "English"
        )

        if event.type == EventType.GREETING:
            return ResponsePlan(
                action=ResponseAction.WELCOME,
                state=context.state,
                language=language,
            )

        if event.type == EventType.SPEAK_TO_TEAM:
            if context.lifecycle.callback_request_sent:
                return ResponsePlan(
                    action=ResponseAction.CALLBACK_ALREADY_RECORDED,
                    state=context.state,
                    language=language,
                )

            return ResponsePlan(
                action=ResponseAction.PROCESS_HANDOFF_REQUEST,
                state=context.state,
                language=language,
            )

        if event.type == EventType.REQUEST_CALLBACK:
            if context.lifecycle.callback_request_sent:
                return ResponsePlan(
                    action=ResponseAction.CALLBACK_ALREADY_RECORDED,
                    state=context.state,
                    language=language,
                )

            return ResponsePlan(
                action=ResponseAction.START_CALLBACK_REQUEST,
                state=context.state,
                language=language,
            )

        if event.type == EventType.CALLBACK_PHONE_VALUE:
            return ResponsePlan(
                action=ResponseAction.ASK_CALLBACK_PREFERENCE,
                state=context.state,
                language=language,
            )

        if event.type == EventType.INVALID_PHONE:
            return ResponsePlan(
                action=ResponseAction.INVALID_PHONE,
                state=context.state,
                language=language,
            )

        if event.type == EventType.CALLBACK_PREFERENCE_VALUE:
            return ResponsePlan(
                action=ResponseAction.PROCESS_CALLBACK_REQUEST,
                state=context.state,
                language=language,
                metadata={
                    "callback_preference":
                        context.customer.callback_preference,
                },
            )

        if event.type == EventType.INVALID_FIELD_VALUE:
            return ResponsePlan(
                action=ResponseAction.ASK_FIELD,
                state=context.state,
                next_field=context.expected_field(),
                options=self._allowed_values(context),
                language=language,
                metadata={
                    "rejected_value": event.value,
                },
            )

        if event.type == EventType.BUSINESS_QUESTION:
            return ResponsePlan(
                action=ResponseAction.ANSWER_BUSINESS_QUESTION,
                state=context.state,
                business_question_type=event.question_type,
                business_question_text=event.question_text,
                current_package=context.quote.package,
                language=language,
            )

        if event.type == EventType.PACKAGE_RECONSIDERATION_REQUEST:
            return ResponsePlan(
                action=ResponseAction.ANSWER_PACKAGE_RECONSIDERATION,
                state=context.state,
                business_question_type=event.question_type,
                business_question_text=event.question_text,
                current_package=context.quote.package,
                options=self._packages_for_current_service(
                    context
                ),
                language=language,
                metadata={
                    "follow_up":
                        ResponseAction
                        .ASK_PACKAGE_RECONFIRMATION
                        .value
                },
            )

        if event.type == EventType.BUSINESS_QUESTION_RESOLVED:
            return self._resume_plan(
                context=context,
                language=language,
            )

        if event.type == EventType.QUOTE_COMPLETED:
            return ResponsePlan(
                action=ResponseAction.ASK_EMAIL_CONFIRMATION,
                state=context.state,
                language=language,
            )

        if event.type == EventType.EMAIL_YES:
            return ResponsePlan(
                action=ResponseAction.ASK_EMAIL_ADDRESS,
                state=context.state,
                language=language,
            )

        if event.type == EventType.EMAIL_NO:
            return ResponsePlan(
                action=ResponseAction.POST_QUOTE_OPTIONS,
                state=context.state,
                language=language,
            )

        if event.type == EventType.EMAIL_ADDRESS_VALUE:
            return ResponsePlan(
                action=ResponseAction.SEND_QUOTE_EMAIL,
                state=context.state,
                language=language,
                metadata={
                    "customer_email":
                        context.customer.email,
                },
            )

        if event.type == EventType.INVALID_EMAIL:
            return ResponsePlan(
                action=ResponseAction.INVALID_EMAIL,
                state=context.state,
                language=language,
            )

        if context.state == FlowState.PACKAGE_RECONFIRMATION:
            if event.type == EventType.PAUSE:
                return ResponsePlan(
                    action=ResponseAction.WAIT_PACKAGE_RECONFIRMATION,
                    state=context.state,
                    current_package=context.quote.package,
                    options=self._packages_for_current_service(
                        context
                    ),
                    language=language,
                )

            return ResponsePlan(
                action=ResponseAction.ASK_PACKAGE_RECONFIRMATION,
                state=context.state,
                current_package=context.quote.package,
                options=self._packages_for_current_service(
                    context
                ),
                language=language,
            )

        if context.state == FlowState.DEFERRED_REVIEW:
            if event.type == EventType.PAUSE:
                return ResponsePlan(
                    action=ResponseAction.PAUSED,
                    state=context.state,
                    deferred_fields=list(
                        context.deferred_fields
                    ),
                    language=language,
                )

            return ResponsePlan(
                action=ResponseAction.REVIEW_DEFERRED_FIELDS,
                state=context.state,
                deferred_fields=list(
                    context.deferred_fields
                ),
                language=language,
            )

        if context.state == FlowState.QUOTE_READY:
            return ResponsePlan(
                action=ResponseAction.QUOTE_READY,
                state=context.state,
                changed_fields=list(
                    transition.changed_fields
                ),
                language=language,
            )

        if context.state == FlowState.EMAIL_CONFIRMATION:
            return ResponsePlan(
                action=ResponseAction.ASK_EMAIL_CONFIRMATION,
                state=context.state,
                language=language,
            )

        if context.state == FlowState.EMAIL_ADDRESS:
            return ResponsePlan(
                action=ResponseAction.ASK_EMAIL_ADDRESS,
                state=context.state,
                language=language,
            )

        if context.state == FlowState.POST_QUOTE:
            return ResponsePlan(
                action=ResponseAction.POST_QUOTE_OPTIONS,
                state=context.state,
                language=language,
            )

        if context.state == FlowState.HANDOFF_OPTIONS:
            return ResponsePlan(
                action=ResponseAction.HANDOFF_OPTIONS,
                state=context.state,
                language=language,
            )

        if context.state == FlowState.CALLBACK_PHONE:
            return ResponsePlan(
                action=ResponseAction.ASK_CALLBACK_PHONE,
                state=context.state,
                language=language,
            )

        if context.state == FlowState.CALLBACK_PREFERENCE:
            return ResponsePlan(
                action=ResponseAction.ASK_CALLBACK_PREFERENCE,
                state=context.state,
                language=language,
            )

        if context.state == FlowState.CALLBACK_RECORDED:
            return ResponsePlan(
                action=ResponseAction.CALLBACK_RECORDED,
                state=context.state,
                language=language,
            )

        if context.state == FlowState.FINISHED:
            return ResponsePlan(
                action=ResponseAction.FINISHED,
                state=context.state,
                language=language,
            )

        if event.type == EventType.PAUSE:
            return ResponsePlan(
                action=ResponseAction.PAUSED,
                state=context.state,
                next_field=context.expected_field(),
                options=self._allowed_values(
                    context
                ),
                language=language,
            )

        if event.type == EventType.UNCLEAR:
            if context.expected_field():
                return ResponsePlan(
                    action=ResponseAction.ASK_FIELD,
                    state=context.state,
                    next_field=context.expected_field(),
                    options=self._allowed_values(
                        context
                    ),
                    deferred_fields=list(
                        context.deferred_fields
                    ),
                    language=language,
                )

        if event.type in {
            EventType.START_QUOTE,
            EventType.START_NEW_QUOTE,
        }:
            return ResponsePlan(
                action=ResponseAction.STARTED_NEW_QUOTE,
                state=context.state,
                next_field=context.expected_field(),
                options=self._allowed_values(
                    context
                ),
                language=language,
            )

        if transition.resume_prompt_required:
            return self._resume_plan(
                context=context,
                language=language,
            )

        if context.expected_field():
            return ResponsePlan(
                action=ResponseAction.ASK_FIELD,
                state=context.state,
                next_field=context.expected_field(),
                options=self._allowed_values(
                    context
                ),
                changed_fields=list(
                    transition.changed_fields
                ),
                language=language,
            )

        return ResponsePlan(
            action=ResponseAction.CLARIFY,
            state=context.state,
            language=language,
        )

    def _resume_plan(
        self,
        *,
        context: ConversationContext,
        language: str,
    ) -> ResponsePlan:
        if context.state == FlowState.PACKAGE_RECONFIRMATION:
            return self.package_reconfirmation_plan(
                context=context,
                language=language,
            )

        if context.state == FlowState.EMAIL_CONFIRMATION:
            return ResponsePlan(
                action=ResponseAction.ASK_EMAIL_CONFIRMATION,
                state=context.state,
                language=language,
            )

        if context.state == FlowState.EMAIL_ADDRESS:
            return ResponsePlan(
                action=ResponseAction.ASK_EMAIL_ADDRESS,
                state=context.state,
                language=language,
            )

        if context.state == FlowState.POST_QUOTE:
            return ResponsePlan(
                action=ResponseAction.POST_QUOTE_OPTIONS,
                state=context.state,
                language=language,
            )

        if context.state == FlowState.IDLE:
            return ResponsePlan(
                action=ResponseAction.WELCOME,
                state=context.state,
                language=language,
            )

        if context.state == FlowState.HANDOFF_OPTIONS:
            return ResponsePlan(
                action=ResponseAction.HANDOFF_OPTIONS,
                state=context.state,
                language=language,
            )

        if context.state == FlowState.CALLBACK_PHONE:
            return ResponsePlan(
                action=ResponseAction.ASK_CALLBACK_PHONE,
                state=context.state,
                language=language,
            )

        if context.state == FlowState.CALLBACK_PREFERENCE:
            return ResponsePlan(
                action=ResponseAction.ASK_CALLBACK_PREFERENCE,
                state=context.state,
                language=language,
            )

        if context.state == FlowState.CALLBACK_RECORDED:
            return ResponsePlan(
                action=ResponseAction.CALLBACK_RECORDED,
                state=context.state,
                language=language,
            )

        if context.expected_field():
            return ResponsePlan(
                action=ResponseAction.RESUME_FIELD,
                state=context.state,
                next_field=context.expected_field(),
                options=self._allowed_values(
                    context
                ),
                language=language,
            )

        if context.state == FlowState.DEFERRED_REVIEW:
            return ResponsePlan(
                action=ResponseAction.REVIEW_DEFERRED_FIELDS,
                state=context.state,
                deferred_fields=list(
                    context.deferred_fields
                ),
                language=language,
            )

        if context.state == FlowState.QUOTE_READY:
            return ResponsePlan(
                action=ResponseAction.QUOTE_READY,
                state=context.state,
                language=language,
            )

        return ResponsePlan(
            action=ResponseAction.CLARIFY,
            state=context.state,
            language=language,
        )

    def package_reconfirmation_plan(
        self,
        *,
        context: ConversationContext,
        language: str = "English",
    ) -> ResponsePlan:
        if context.state != FlowState.PACKAGE_RECONFIRMATION:
            raise ValueError(
                "Package reconfirmation plan requires "
                "PACKAGE_RECONFIRMATION state."
            )

        return ResponsePlan(
            action=ResponseAction.ASK_PACKAGE_RECONFIRMATION,
            state=context.state,
            current_package=context.quote.package,
            options=self._packages_for_current_service(
                context
            ),
            language=language,
        )

    # ------------------------------------------------------------------
    # Catalogue helpers
    # ------------------------------------------------------------------

    def _packages_for_current_service(
        self,
        context: ConversationContext,
    ) -> list[str]:
        return list(
            self.packages_by_service.get(
                context.quote.service or "",
                [],
            )
        )

    def _allowed_values(
        self,
        context: ConversationContext,
    ) -> list[str]:
        state = context.state

        if state == FlowState.QUOTE_SERVICE:
            return list(
                self.supported_services
            )

        if state == FlowState.QUOTE_PACKAGE:
            return self._packages_for_current_service(
                context
            )

        if state == FlowState.QUOTE_COVERAGE:
            return [
                "Photography",
                "Videography",
                "Both",
            ]

        if state == FlowState.QUOTE_TRAVEL:
            return [
                "Yes",
                "No",
            ]

        if state == FlowState.PACKAGE_RECONFIRMATION:
            return self._packages_for_current_service(
                context
            )

        return []


class ConversationOrchestratorError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        turn_log: dict,
    ):
        super().__init__(
            message
        )

        self.turn_log = turn_log
