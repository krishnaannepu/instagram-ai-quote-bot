from __future__ import annotations

from dataclasses import dataclass

from business_question_coordinator_v3 import (
    BusinessQuestionCoordinatorV3,
)
from conversation_models import ConversationContext
from conversation_orchestrator import ConversationOrchestrator
from customer_response_renderer_v3 import (
    CustomerResponseRendererV3,
    RenderedMessage,
)
from email_delivery_adapter_v3 import (
    EmailDeliveryAdapterError,
    EmailDeliveryAdapterV3,
)
from handoff_callback_service_v3 import (
    HandoffCallbackServiceV3,
)
from quote_completion_service_v3 import (
    QuoteCompletionServiceV3,
)
from response_plan import (
    ResponseAction,
    ResponsePlan,
)


@dataclass
class RuntimeTurnResult:
    messages: list[RenderedMessage]
    quote: dict | None
    turn_log: dict


class LocalConversationRuntimeV3:
    """
    Complete channel-independent V3 runtime.

    Instagram transport remains outside this class.
    """

    def __init__(
        self,
        *,
        orchestrator:
            ConversationOrchestrator,
        business_coordinator:
            BusinessQuestionCoordinatorV3,
        quote_completion:
            QuoteCompletionServiceV3,
        email_delivery:
            EmailDeliveryAdapterV3,
        handoff_service:
            HandoffCallbackServiceV3 | None = None,
        renderer:
            CustomerResponseRendererV3 | None = None,
    ):
        self.orchestrator = (
            orchestrator
        )
        self.business_coordinator = (
            business_coordinator
        )
        self.quote_completion = (
            quote_completion
        )
        self.email_delivery = (
            email_delivery
        )
        self.handoff_service = (
            handoff_service
        )
        self.renderer = (
            renderer
            or CustomerResponseRendererV3()
        )

    def handle_text(
        self,
        *,
        context: ConversationContext,
        message_text: str,
    ) -> RuntimeTurnResult:
        result = (
            self.orchestrator
            .handle_text(
                context=context,
                message_text=message_text,
            )
        )

        return self._complete(
            context=context,
            result=result,
        )

    def handle_button(
        self,
        *,
        context: ConversationContext,
        payload: str,
    ) -> RuntimeTurnResult:
        result = (
            self.orchestrator
            .handle_button(
                context=context,
                payload=payload,
            )
        )

        return self._complete(
            context=context,
            result=result,
        )

    def _complete(
        self,
        *,
        context: ConversationContext,
        result,
    ) -> RuntimeTurnResult:
        plan = (
            result.response_plan
        )

        if (
            plan.action
            == ResponseAction
            .ANSWER_BUSINESS_QUESTION
        ):
            resolution = (
                self.business_coordinator
                .resolve(
                    context=context,
                    question_text=
                        plan.business_question_text
                        or "",
                    question_type=
                        plan.business_question_type,
                    customer_language=
                        plan.language,
                )
            )

            messages = (
                self.renderer
                .render_business_answer(
                    answer=
                        resolution.answer,
                    follow_up=
                        resolution.resume_plan,
                )
            )

            return RuntimeTurnResult(
                messages=messages,
                quote=None,
                turn_log=
                    result.turn_log,
            )

        if (
            plan.action
            == ResponseAction
            .ANSWER_PACKAGE_RECONSIDERATION
        ):
            resolution = (
                self.business_coordinator
                .resolve_package_reconsideration(
                    context=context,
                    question_text=
                        plan.business_question_text
                        or "",
                    question_type=
                        plan.business_question_type,
                    customer_language=
                        plan.language,
                )
            )

            messages = (
                self.renderer
                .render_business_answer(
                    answer=
                        resolution.answer,
                    follow_up=
                        resolution.resume_plan,
                )
            )

            return RuntimeTurnResult(
                messages=messages,
                quote=None,
                turn_log=
                    result.turn_log,
            )

        if (
            plan.action
            == ResponseAction.QUOTE_READY
        ):
            completion = (
                self.quote_completion
                .complete(
                    context=context
                )
            )

            return RuntimeTurnResult(
                messages=[
                    self.renderer.render_quote(
                        completion.quote
                    ),
                    self.renderer.render_plan(
                        completion.next_plan
                    ),
                ],
                quote=
                    completion.quote,
                turn_log=
                    result.turn_log,
            )

        if (
            plan.action
            == ResponseAction
            .SEND_QUOTE_EMAIL
        ):
            try:
                self.email_delivery.send_customer_quote(
                    context=context
                )

                email_plan = ResponsePlan(
                    action=
                        ResponseAction
                        .EMAIL_SENT,
                    state=
                        context.state,
                )

            except EmailDeliveryAdapterError:
                email_plan = ResponsePlan(
                    action=
                        ResponseAction
                        .EMAIL_FAILED,
                    state=
                        context.state,
                )

            post_quote_plan = ResponsePlan(
                action=
                    ResponseAction
                    .POST_QUOTE_OPTIONS,
                state=
                    context.state,
            )

            return RuntimeTurnResult(
                messages=[
                    self.renderer.render_plan(
                        email_plan
                    ),
                    self.renderer.render_plan(
                        post_quote_plan
                    ),
                ],
                quote=
                    context.lifecycle.quote_data
                    or None,
                turn_log=
                    result.turn_log,
            )

        if (
            plan.action
            == ResponseAction
            .PROCESS_HANDOFF_REQUEST
        ):
            if not self.handoff_service:
                raise RuntimeError(
                    "Handoff service is not configured."
                )

            outcome = (
                self.handoff_service
                .process_handoff(
                    context=context
                )
            )

            handoff_plan = ResponsePlan(
                action=
                    ResponseAction
                    .HANDOFF_OPTIONS,
                state=
                    context.state,
                metadata={
                    "office_open":
                        outcome.office_open,
                    "business_phone":
                        outcome.business_phone,
                    "already_requested":
                        outcome.already_requested,
                },
            )

            return RuntimeTurnResult(
                messages=[
                    self.renderer.render_plan(
                        handoff_plan
                    )
                ],
                quote=
                    context.lifecycle.quote_data
                    or None,
                turn_log=
                    result.turn_log,
            )

        if (
            plan.action
            == ResponseAction
            .START_CALLBACK_REQUEST
        ):
            if not self.handoff_service:
                raise RuntimeError(
                    "Handoff service is not configured."
                )

            callback_start = (
                self.handoff_service
                .start_callback(
                    context=context
                )
            )

            callback_plan = ResponsePlan(
                action=(
                    ResponseAction
                    .CALLBACK_ALREADY_RECORDED
                    if callback_start
                    .already_recorded
                    else ResponseAction
                    .ASK_CALLBACK_PHONE
                ),
                state=
                    context.state,
            )

            return RuntimeTurnResult(
                messages=[
                    self.renderer.render_plan(
                        callback_plan
                    )
                ],
                quote=
                    context.lifecycle.quote_data
                    or None,
                turn_log=
                    result.turn_log,
            )

        if (
            plan.action
            == ResponseAction
            .PROCESS_CALLBACK_REQUEST
        ):
            if not self.handoff_service:
                raise RuntimeError(
                    "Handoff service is not configured."
                )

            callback_result = (
                self.handoff_service
                .complete_callback(
                    context=context
                )
            )

            callback_plan = ResponsePlan(
                action=
                    ResponseAction
                    .CALLBACK_RECORDED,
                state=
                    context.state,
                metadata={
                    "office_open":
                        callback_result
                        .office_open,
                    "notification_sent":
                        callback_result
                        .notification_sent,
                },
            )

            return RuntimeTurnResult(
                messages=[
                    self.renderer.render_plan(
                        callback_plan
                    )
                ],
                quote=
                    context.lifecycle.quote_data
                    or None,
                turn_log=
                    result.turn_log,
            )

        return RuntimeTurnResult(
            messages=[
                self.renderer.render_plan(
                    plan
                )
            ],
            quote=None,
            turn_log=
                result.turn_log,
        )
