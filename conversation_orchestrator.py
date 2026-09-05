from __future__ import annotations

import re
from copy import deepcopy
from dataclasses import dataclass, replace
from typing import Protocol

from conversation_events import ConversationEvent, EventType
from conversation_models import (
    QUOTE_FIELD_ORDER,
    QUOTE_STATE_TO_FIELD,
    ConversationContext,
    FlowState,
)
from conversation_state_machine import (
    ConversationStateMachine,
    TransitionResult,
)
from event_normalizer import EventNormalizer
from response_plan import ResponseAction, ResponsePlan
from semantic_contract import (
    QUOTE_EDITABLE_STATES,
    SemanticAction,
    SemanticInterpretation,
)
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
        # Asking to stop must always work - in any state, and even if the
        # model is unavailable or the state parses its own input. This runs
        # before everything else for that reason.
        deterministic_finish = self._try_finish_input(
            context=context,
            message_text=message_text,
        )

        if deterministic_finish is not None:
            return deterministic_finish

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

            interpretation = self._route_field_intent(
                context=context,
                interpretation=interpretation,
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

    def _route_field_intent(
        self,
        *,
        context: ConversationContext,
        interpretation: SemanticInterpretation,
    ) -> SemanticInterpretation:
        """
        Decide what a quote value means for the state we are actually in.

        The adapter reports which field the customer named. Python decides
        whether that is an answer to the question being asked, or a detail
        volunteered out of sequence.

        - at IDLE a quote value starts the quote, so a customer who types
          what they want does not have to tap a button first;
        - a value for the field being asked stays FIELD_VALUE and advances;
        - a value for any other field becomes a change: record it, keep
          asking for what is still missing.

        Without this, anything said out of order reached the customer as a
        failed turn.
        """

        if interpretation.action not in {
            SemanticAction.FIELD_VALUE,
            SemanticAction.CHANGE_FIELD,
        }:
            return interpretation

        has_field = interpretation.field_name in QUOTE_FIELD_ORDER

        has_value = interpretation.value not in {
            None,
            "",
        }

        changes = list(
            interpretation.changes
        )

        if not changes and has_field and has_value:
            changes = [
                {
                    "field_name":
                        interpretation.field_name,
                    "value":
                        interpretation.value,
                }
            ]

        # Several details in one message: apply them all. field_name/value
        # stay set to the first so every existing single-change path still
        # works unchanged.
        if len(changes) > 1:
            if context.state == FlowState.IDLE:
                context.reset_for_new_quote()

            return replace(
                interpretation,
                action=SemanticAction.CHANGE_FIELD,
                field_name=changes[0]["field_name"],
                value=changes[0]["value"],
                changes=changes,
            )

        if changes:
            interpretation = replace(
                interpretation,
                field_name=changes[0]["field_name"],
                value=changes[0]["value"],
                changes=[],
            )
            has_field = True
            has_value = True

        # "Can I change something?" names no field. "Change the package"
        # names no value. Both are ordinary messages, not broken output -
        # ask what they want to change, or what to change it to.
        if not (has_field and has_value):
            return replace(
                interpretation,
                action=SemanticAction.CHANGE_REQUEST,
                field_name=(
                    interpretation.field_name
                    if has_field
                    else None
                ),
                value=None,
            )

        if context.state == FlowState.IDLE:
            context.reset_for_new_quote()

        expected_field = context.expected_field()

        if expected_field is None:
            # No field is being asked for. In a state where the quote can
            # still be edited - after pricing, at the email step, post-quote -
            # any value the customer gives is a change to that field.
            # Callback and handoff flows own their own input, so leave those.
            if context.state in QUOTE_EDITABLE_STATES:
                return replace(
                    interpretation,
                    action=SemanticAction.CHANGE_FIELD,
                )

            return interpretation

        if (
            interpretation.action == SemanticAction.FIELD_VALUE
            and interpretation.field_name != expected_field
        ):
            return replace(
                interpretation,
                action=SemanticAction.CHANGE_FIELD,
            )

        return interpretation

    def _guard_catalogue_value(
        self,
        *,
        context: ConversationContext,
        interpretation: SemanticInterpretation,
    ) -> tuple[SemanticInterpretation, ConversationEvent | None]:
        if interpretation.action == SemanticAction.FIELD_VALUE:
            # States that expect no field return nothing here, which
            # would leave the value unvalidated. Fall back to the field.
            allowed_values = (
                self._allowed_values(context)
                or self._allowed_values_for_field(
                    context,
                    interpretation.field_name,
                )
            )

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

        if (
            interpretation.action == SemanticAction.CHANGE_FIELD
            and interpretation.changes
        ):
            accepted = []
            rejected = []

            # One message can change the service and the package together.
            # The package has to be checked against the service the customer
            # is moving to, not the one they are leaving, or a valid package
            # for the new service is rejected as unknown.
            pending_service = None

            for change in interpretation.changes:
                if change["field_name"] != "service":
                    continue

                pending_service = self._canonical_allowed_value(
                    change["value"],
                    list(
                        self.supported_services
                    ),
                )

            for change in interpretation.changes:
                field_name = change["field_name"]

                if (
                    field_name == "package"
                    and pending_service
                ):
                    allowed_values = list(
                        self.packages_by_service.get(
                            pending_service,
                            [],
                        )
                    )
                else:
                    allowed_values = self._allowed_values_for_field(
                        context,
                        field_name,
                    )

                if not allowed_values:
                    accepted.append(change)
                    continue

                canonical = self._canonical_allowed_value(
                    change["value"],
                    allowed_values,
                )

                if canonical is None:
                    rejected.append(change)
                    continue

                accepted.append(
                    {
                        "field_name": field_name,
                        "value": canonical,
                    }
                )

            # Nothing usable left: reject as a single bad value.
            if not accepted:
                first = interpretation.changes[0]

                return (
                    interpretation,
                    ConversationEvent(
                        type=EventType.INVALID_FIELD_VALUE,
                        field=first["field_name"],
                        value=first["value"],
                        metadata={
                            "source": "python_catalogue_guard",
                            "allowed_values": list(
                                self._allowed_values_for_field(
                                    context,
                                    first["field_name"],
                                )
                            ),
                        },
                    ),
                )

            return (
                replace(
                    interpretation,
                    field_name=accepted[0]["field_name"],
                    value=accepted[0]["value"],
                    changes=accepted,
                    metadata={
                        **interpretation.metadata,
                        "rejected_changes": rejected,
                    },
                ),
                None,
            )

        if interpretation.action == SemanticAction.CHANGE_FIELD:
            allowed_values = self._allowed_values_for_field(
                context,
                interpretation.field_name,
            )

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
                            field=interpretation.field_name,
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
        normalized = str(value or "").strip().casefold()

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

    # Whole-message matches only. "stop by the studio" is a location, and
    # "don't finish yet" is not a request to end - neither may trigger this.
    FINISH_PHRASES = frozenset({
        "stop",
        "stop it",
        "stop please",
        "please stop",
        "finish",
        "finished",
        "im finished",
        "i am finished",
        "im done",
        "i am done",
        "done",
        "thats all",
        "that is all",
        "thats it",
        "that is it",
        "nothing else",
        "no thanks bye",
        "cancel",
        "cancel it",
        "cancel please",
        "end",
        "end chat",
        "end it",
        "exit",
        "quit",
        "close",
        "close chat",
        "bye",
        "byee",
        "goodbye",
        "good bye",
        "bye bye",
        "bye thanks",
        "thanks bye",
        "ok bye",
        "okay bye",
        "alright bye",
        "bas",
        "bas karo",
        "khatam",
        "band karo",
        "chalo bye",
        "aapko dhanyavaad",
        "aagipo",
        "chaalu",
    })

    def _try_finish_input(
        self,
        *,
        context: ConversationContext,
        message_text: str,
    ) -> OrchestratorResult | None:
        text = str(
            message_text
            or ""
        ).strip().casefold()

        # Drop apostrophes rather than splitting on them, so "that's all"
        # normalises to "thats all" and not "that s all".
        text = re.sub(
            r"['\u2019\u02bc]",
            "",
            text,
        )

        normalized = " ".join(
            re.sub(
                r"[^a-z0-9\s]",
                " ",
                text,
            ).split()
        )

        if normalized not in self.FINISH_PHRASES:
            return None

        before = deepcopy(
            context
        )

        event = ConversationEvent(
            type=EventType.FINISH,
            metadata={
                "source": "deterministic_finish_parser",
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
        self._invalidate_dependent_fields(
            context=context,
            event=event,
        )

        plan = self._plan_response_base(
            context=context,
            interpretation=interpretation,
            event=event,
            transition=transition,
        )

        # A customer who asks to change something has to be told what
        # happened to it. Without this the bot silently repeats the next
        # question, which reads as being ignored.
        if event.type == EventType.CHANGE_FIELD:
            plan = replace(
                plan,
                metadata={
                    **plan.metadata,
                    "changed_field": event.field,
                    "changed_value": context.quote.get(
                        event.field
                    ),
                    "change_applied": bool(
                        transition.changed_fields
                    ),
                    "changed_fields": [
                        {
                            "field_name": field_name,
                            "value": context.quote.get(
                                field_name
                            ),
                        }
                        for field_name in (
                            change.get("field_name")
                            for change in
                            event.metadata.get("changes")
                            or []
                        )
                        if field_name
                    ],
                    "rejected_changes":
                        event.metadata.get(
                            "rejected_changes"
                        )
                        or [],
                },
            )

        return plan

    def _invalidate_dependent_fields(
        self,
        *,
        context: ConversationContext,
        event: ConversationEvent,
    ) -> str | None:
        """
        Changing the service can strand a package that does not exist for the
        new service.

        expected_field() is derived from the state, not from what is missing,
        so clearing the package is not enough - the flow has to rewind to it
        or the quote reaches pricing with a package the catalogue never had.
        """

        if event.field != "service":
            return None

        if event.type not in {
            EventType.FIELD_VALUE,
            EventType.CHANGE_FIELD,
        }:
            return None

        package = context.quote.package

        if not package:
            return None

        allowed_packages = self._packages_for_current_service(
            context
        )

        if self._canonical_allowed_value(
            package,
            allowed_packages,
        ) is not None:
            return None

        context.quote.set(
            "package",
            None,
        )

        if context.state in QUOTE_STATE_TO_FIELD or context.state in {
            FlowState.QUOTE_READY,
            FlowState.EMAIL_CONFIRMATION,
            FlowState.EMAIL_ADDRESS,
            FlowState.POST_QUOTE,
        }:
            context.state = FlowState.QUOTE_PACKAGE

        return "package"

    def _plan_response_base(
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
            # Welcome only when there is nothing under way. Mid-quote, a
            # greeting must not look like the conversation restarted - pick
            # up the question the customer still owes us an answer to.
            if context.state != FlowState.IDLE:
                return self._resume_plan(
                    context=context,
                    language=language,
                )

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
                    "rejected_field": (
                        event.field
                        or context.expected_field()
                    ),
                    "rejected_options":
                        self._allowed_values_for_field(
                            context,
                            event.field
                            or context.expected_field(),
                        ),
                },
            )

        if event.type == EventType.CHANGE_REQUEST:
            return ResponsePlan(
                action=ResponseAction.ASK_WHAT_TO_CHANGE,
                state=context.state,
                next_field=context.expected_field(),
                options=self._allowed_values_for_field(
                    context,
                    event.field,
                ),
                current_package=context.quote.package,
                language=language,
                metadata={
                    "quote_summary":
                        context.quote.as_dict(),
                    "change_field":
                        event.field,
                },
            )

        if event.type == EventType.STATUS_QUESTION:
            return ResponsePlan(
                action=ResponseAction.ANSWER_STATUS,
                state=context.state,
                next_field=context.expected_field(),
                options=self._allowed_values(
                    context
                ),
                current_package=context.quote.package,
                language=language,
                metadata={
                    "quote_summary":
                        context.quote.as_dict(),
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
            if context.state == FlowState.IDLE:
                # A business question asked before any quote was started
                # resolves back to IDLE. Do not repeat the first-contact
                # greeting - the customer already engaged.
                return ResponsePlan(
                    action=ResponseAction.WELCOME_BACK,
                    state=context.state,
                    language=language,
                )

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

    def _allowed_values_for_field(
        self,
        context: ConversationContext,
        field_name: str | None,
    ) -> list[str]:
        """
        Allowed values for a NAMED field.

        _allowed_values() answers for the state's expected field. A
        CHANGE_FIELD can target a field the state is not currently asking
        for, so its validation has to key off the field, not the state.
        """

        if field_name == "service":
            return list(
                self.supported_services
            )

        if field_name == "package":
            return self._packages_for_current_service(
                context
            )

        if field_name == "coverage_type":
            return [
                "Photography",
                "Videography",
                "Both",
            ]

        if field_name == "travel_required":
            return [
                "Yes",
                "No",
            ]

        return []

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
