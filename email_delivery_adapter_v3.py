from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from conversation_models import ConversationContext
from lead_persistence_adapter_v3 import LeadPersistenceAdapterV3


class EmailDeliveryAdapterError(RuntimeError):
    pass


class EmailDeliveryAdapterV3:
    """
    Reuses only the existing generic Gmail transport for customer emails.

    The legacy customer quote email is intentionally not reused because V3
    owns the customer-facing wording and copy constraints.
    """

    def __init__(
        self,
        *,
        project_root: Path | None = None,
        email_module=None,
        lead_persistence:
            LeadPersistenceAdapterV3 | None = None,
    ):
        self.project_root = (
            Path(project_root).resolve()
            if project_root
            else Path(__file__).resolve().parent.parent
        )
        self._email_module = email_module
        self.lead_persistence = (
            lead_persistence
        )

    def _service(
        self,
    ):
        if self._email_module is not None:
            return self._email_module

        root = str(
            self.project_root
        )

        if root not in sys.path:
            sys.path.insert(
                0,
                root,
            )

        try:
            import email_service
        except Exception as error:
            raise EmailDeliveryAdapterError(
                "Could not import existing email_service.py."
            ) from error

        self._email_module = (
            email_service
        )

        return self._email_module

    def send_customer_quote(
        self,
        *,
        context: ConversationContext,
    ) -> dict[str, Any]:
        customer_email = (
            context.customer.email
        )

        quote_data = (
            context.lifecycle.quote_data
        )

        if not customer_email:
            raise EmailDeliveryAdapterError(
                "Customer email is missing."
            )

        if not quote_data:
            raise EmailDeliveryAdapterError(
                "Quote data is missing."
            )

        subject = (
            "Your Quote - "
            f"{context.quote.service or 'Event'} - "
            f"£{float(quote_data.get('quote_total', 0)):,.2f}"
        )

        body = self._build_customer_body(
            context=context,
            quote_data=quote_data,
        )

        try:
            result = self._service().send_email(
                recipient=customer_email,
                subject=subject,
                body=body,
            )
        except Exception as error:
            if self.lead_persistence:
                try:
                    self.lead_persistence.update_status(
                        context=context,
                        status="EMAIL_SEND_FAILED",
                        extra_updates={
                            "customer_email":
                                customer_email,
                        },
                    )
                except Exception:
                    pass

            raise EmailDeliveryAdapterError(
                "Could not send customer quote email."
            ) from error

        context.lifecycle.quote_email_sent = (
            True
        )

        if self.lead_persistence:
            self.lead_persistence.update_status(
                context=context,
                status="QUOTE_EMAILED",
                extra_updates={
                    "customer_email":
                        customer_email,
                },
            )

        return result

    def send_new_lead_notification(
        self,
        *,
        context: ConversationContext,
        quote_data: dict[str, Any],
        lead_data: dict[str, Any],
    ) -> dict[str, Any] | None:
        """
        Existing owner notification is internal, so it may reuse the existing
        production helper.
        """

        service = self._service()

        if not hasattr(
            service,
            "send_new_lead_email",
        ):
            return None

        session = self._build_legacy_session(
            context=context,
            quote_data=quote_data,
        )

        try:
            return service.send_new_lead_email(
                session=session,
                quote=quote_data,
                lead=lead_data,
            )
        except Exception:
            # Owner notification failure must not destroy a valid customer
            # quote flow.
            return None

    def send_handoff_notification(
        self,
        *,
        context: ConversationContext,
        office_open: bool,
        business_phone: str = "",
    ) -> dict[str, Any] | None:
        service = self._service()

        if not hasattr(
            service,
            "send_handoff_notification",
        ):
            return None

        session = self._build_legacy_session(
            context=context,
            quote_data=(
                context.lifecycle.quote_data
                or {}
            ),
        )

        session.update(
            {
                "customer_phone":
                    context.customer.phone,
                "callback_preference":
                    context.customer.callback_preference,
            }
        )

        lead = (
            context.lifecycle.lead_data
            or {
                "lead_id":
                    context.lifecycle.active_lead_id,
            }
        )

        try:
            result = service.send_handoff_notification(
                session=session,
                lead=lead,
                office_open=office_open,
                business_phone=business_phone,
            )
        except Exception as error:
            raise EmailDeliveryAdapterError(
                "Could not send handoff notification."
            ) from error

        context.lifecycle.handoff_notification_sent = True

        return result

    def send_callback_notification(
        self,
        *,
        context: ConversationContext,
    ) -> dict[str, Any] | None:
        service = self._service()

        if not hasattr(
            service,
            "send_callback_request_email",
        ):
            return None

        session = self._build_legacy_session(
            context=context,
            quote_data=(
                context.lifecycle.quote_data
                or {}
            ),
        )

        session.update(
            {
                "customer_phone":
                    context.customer.phone,
                "callback_preference":
                    context.customer.callback_preference,
            }
        )

        lead = (
            context.lifecycle.lead_data
            or {
                "lead_id":
                    context.lifecycle.active_lead_id,
            }
        )

        try:
            result = service.send_callback_request_email(
                session=session,
                lead=lead,
            )
        except Exception as error:
            raise EmailDeliveryAdapterError(
                "Could not send callback notification."
            ) from error

        context.lifecycle.callback_notification_sent = True

        return result

    def _build_customer_body(
        self,
        *,
        context: ConversationContext,
        quote_data: dict[str, Any],
    ) -> str:
        lead_id = (
            context.lifecycle.lead_data.get(
                "lead_id",
                "",
            )
        )

        quote = context.quote

        extra_hours = float(
            quote_data.get(
                "extra_hours",
                0,
            )
            or 0
        )

        lines = [
            "Thank you for your enquiry.",
            "",
            "Your estimated quote details are below.",
            "",
        ]

        if lead_id:
            lines.append(
                f"Reference: {lead_id}"
            )

        lines.extend(
            [
                f"Service: {quote.service or ''}",
                f"Package: {quote.package or ''}",
                f"Coverage: {quote.coverage_type or ''}",
                f"Event Date: {quote.event_date or ''}",
                f"Location: {quote.location or ''}",
                f"Duration: {self._fmt_number(quote.duration_hours)} hours",
                f"Travel Required: {quote.travel_required or ''}",
                "",
                "Pricing",
                "------------------------------",
                f"Base Price: £{self._fmt_money(quote_data.get('base_price'))}",
            ]
        )

        if extra_hours > 0:
            extra_rate = quote_data.get(
                "extra_hour_rate",
                0,
            )

            extra_cost = quote_data.get(
                "extra_hours_cost",
                extra_hours
                * float(
                    extra_rate
                    or 0
                ),
            )

            lines.extend(
                [
                    f"Extra Hours: {self._fmt_number(extra_hours)}",
                    f"Extra Hour Rate: £{self._fmt_money(extra_rate)}",
                    f"Extra Hours Cost: £{self._fmt_money(extra_cost)}",
                ]
            )

        travel_fee = float(
            quote_data.get(
                "travel_fee",
                0,
            )
            or 0
        )

        lines.append(
            f"Travel Fee: £{self._fmt_money(travel_fee)}"
        )

        lines.extend(
            [
                "",
                f"Estimated Total: £{self._fmt_money(quote_data.get('quote_total'))}",
                "",
                "Final pricing and availability may require confirmation from our team.",
                "",
                "Thank you.",
            ]
        )

        body = "\n".join(
            lines
        )

        # Customer-facing hard guard.
        if "smileshoots" in body.lower():
            raise EmailDeliveryAdapterError(
                "Customer email contains prohibited business name."
            )

        if "testing" in body.lower():
            raise EmailDeliveryAdapterError(
                "Customer email contains prohibited customer-facing term."
            )

        return body

    def _build_legacy_session(
        self,
        *,
        context: ConversationContext,
        quote_data: dict[str, Any],
    ) -> dict[str, Any]:
        quote = context.quote

        return {
            "sender_id":
                context.metadata.get(
                    "sender_id",
                    "",
                ),
            "service":
                quote.service
                or "",
            "package":
                quote.package
                or "",
            "coverage_type":
                quote.coverage_type
                or "",
            "event_date":
                quote.event_date
                or "",
            "location":
                quote.location
                or "",
            "duration_hours":
                quote.duration_hours
                if quote.duration_hours is not None
                else "",
            "travel_required":
                quote.travel_required
                or "",
            "customer_email":
                context.customer.email,
            "customer_phone":
                context.customer.phone,
            "callback_preference":
                context.customer.callback_preference,
            "handoff_requested":
                "Yes"
                if context.lifecycle.handoff_requested
                else "",
            "handoff_requested_at":
                context.lifecycle.handoff_requested_at,
            "handoff_status":
                context.lifecycle.handoff_status,
            "quote_data":
                quote_data,
        }

    def _fmt_money(
        self,
        value,
    ) -> str:
        return f"{float(value or 0):,.2f}"

    def _fmt_number(
        self,
        value,
    ) -> str:
        number = float(
            value
            or 0
        )

        if number.is_integer():
            return str(
                int(
                    number
                )
            )

        return f"{number:g}"
