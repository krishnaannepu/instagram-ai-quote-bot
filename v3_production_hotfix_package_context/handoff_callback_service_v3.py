from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from conversation_models import ConversationContext
from email_delivery_adapter_v3 import (
    EmailDeliveryAdapterError,
    EmailDeliveryAdapterV3,
)
from lead_persistence_adapter_v3 import (
    LeadPersistenceAdapterV3,
)


@dataclass(frozen=True)
class HandoffResult:
    office_open: bool
    business_phone: str
    already_requested: bool


@dataclass(frozen=True)
class CallbackStartResult:
    already_recorded: bool


@dataclass(frozen=True)
class CallbackCompletionResult:
    office_open: bool
    notification_sent: bool


class HandoffCallbackServiceV3:
    """
    Human-contact lifecycle without conversation routing.

    Python owns:
    - duplicate prevention
    - lead status updates
    - office-hours determination
    - email notification calls

    The conversation state machine owns the state itself.
    """

    def __init__(
        self,
        *,
        lead_persistence: LeadPersistenceAdapterV3,
        email_delivery: EmailDeliveryAdapterV3,
        business_phone: str | None = None,
        now_provider=None,
    ):
        self.lead_persistence = lead_persistence
        self.email_delivery = email_delivery
        self.business_phone = (
            business_phone
            if business_phone is not None
            else os.getenv(
                "BUSINESS_PHONE_NUMBER",
                "",
            )
        ).strip()

        self.now_provider = (
            now_provider
            or (
                lambda: datetime.now(
                    ZoneInfo(
                        "Europe/London"
                    )
                )
            )
        )

    def is_office_open(
        self,
    ) -> bool:
        """
        Preserve the existing production behavior: 9 <= UK hour < 17.

        The old implementation did not separately check weekday/weekend.
        """

        uk_now = self.now_provider()

        return (
            9
            <= uk_now.hour
            < 17
        )

    def process_handoff(
        self,
        *,
        context: ConversationContext,
    ) -> HandoffResult:
        lifecycle = (
            context.lifecycle
        )

        office_open = (
            self.is_office_open()
        )

        already_requested = (
            lifecycle.handoff_requested
        )

        if already_requested:
            return HandoffResult(
                office_open=office_open,
                business_phone=
                    self.business_phone,
                already_requested=True,
            )

        lifecycle.handoff_requested = True
        lifecycle.handoff_requested_at = (
            self._utc_timestamp()
        )
        lifecycle.handoff_status = (
            "REQUESTED"
        )

        self.lead_persistence.ensure_handoff_lead(
            context=context,
            status="HUMAN_HANDOFF",
        )

        try:
            self.lead_persistence.update_status(
                context=context,
                status="HUMAN_HANDOFF",
                extra_updates={
                    "human_handoff":
                        True,
                    "handoff_requested":
                        "Yes",
                    "handoff_requested_at":
                        lifecycle
                        .handoff_requested_at,
                    "handoff_status":
                        "REQUESTED",
                },
            )
        except Exception:
            # The customer handoff should still continue even if a secondary
            # sheet update fails after a lead exists.
            pass

        if not lifecycle.handoff_notification_sent:
            try:
                self.email_delivery.send_handoff_notification(
                    context=context,
                    office_open=office_open,
                    business_phone=
                        self.business_phone,
                )
            except EmailDeliveryAdapterError:
                pass

        # Preserve previous behavior: if the final quote and customer email
        # are already known, human handoff should not prevent quote delivery.
        if (
            context.customer.email
            and lifecycle.quote_data
            and not lifecycle.quote_email_sent
        ):
            try:
                self.email_delivery.send_customer_quote(
                    context=context
                )
            except EmailDeliveryAdapterError:
                pass

        return HandoffResult(
            office_open=office_open,
            business_phone=
                self.business_phone,
            already_requested=False,
        )

    def start_callback(
        self,
        *,
        context: ConversationContext,
    ) -> CallbackStartResult:
        lifecycle = (
            context.lifecycle
        )

        if lifecycle.callback_request_sent:
            return CallbackStartResult(
                already_recorded=True
            )

        if not lifecycle.handoff_requested:
            lifecycle.handoff_requested = (
                True
            )

        if not lifecycle.handoff_requested_at:
            lifecycle.handoff_requested_at = (
                self._utc_timestamp()
            )

        lifecycle.handoff_status = (
            "AWAITING_CALLBACK_PHONE"
        )

        self.lead_persistence.ensure_handoff_lead(
            context=context,
            status="AWAITING_CALLBACK_PHONE",
        )

        return CallbackStartResult(
            already_recorded=False
        )

    def complete_callback(
        self,
        *,
        context: ConversationContext,
    ) -> CallbackCompletionResult:
        lifecycle = (
            context.lifecycle
        )

        if lifecycle.callback_request_sent:
            return CallbackCompletionResult(
                office_open=
                    self.is_office_open(),
                notification_sent=
                    lifecycle
                    .callback_notification_sent,
            )

        if not context.customer.phone:
            raise ValueError(
                "Callback phone is missing."
            )

        if not context.customer.callback_preference:
            raise ValueError(
                "Callback preference is missing."
            )

        if not lifecycle.handoff_requested:
            lifecycle.handoff_requested = True

        if not lifecycle.handoff_requested_at:
            lifecycle.handoff_requested_at = (
                self._utc_timestamp()
            )

        lifecycle.handoff_status = (
            "CALLBACK_REQUESTED"
        )

        self.lead_persistence.ensure_handoff_lead(
            context=context,
            status="CALLBACK_REQUESTED",
        )

        try:
            self.lead_persistence.update_status(
                context=context,
                status="CALLBACK_REQUESTED",
                extra_updates={
                    "customer_phone":
                        context.customer.phone,
                    "callback_preference":
                        context.customer
                        .callback_preference,
                    "human_handoff":
                        True,
                    "handoff_requested":
                        "Yes",
                    "handoff_requested_at":
                        lifecycle
                        .handoff_requested_at,
                    "handoff_status":
                        "CALLBACK_REQUESTED",
                },
            )
        except Exception:
            pass

        notification_sent = False

        try:
            self.email_delivery.send_callback_notification(
                context=context
            )
            notification_sent = True
        except EmailDeliveryAdapterError:
            notification_sent = False

        # Preserve duplicate protection even if notification transport fails:
        # the request itself has been recorded in session/lead state.
        lifecycle.callback_request_sent = (
            True
        )

        lifecycle.callback_notification_sent = (
            notification_sent
        )

        return CallbackCompletionResult(
            office_open=
                self.is_office_open(),
            notification_sent=
                notification_sent,
        )

    def _utc_timestamp(
        self,
    ) -> str:
        return datetime.now(
            timezone.utc
        ).isoformat()
