from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from conversation_models import ConversationContext


class LeadPersistenceAdapterError(RuntimeError):
    pass


@dataclass(frozen=True)
class LeadPersistenceResult:
    lead: dict[str, Any]
    created_new: bool


class LeadPersistenceAdapterV3:
    """
    Adapter over the existing Leads-sheet functions.

    V3 does not reuse the legacy conversation-stage persistence model.
    """

    def __init__(
        self,
        *,
        project_root: Path | None = None,
        sheets_module=None,
    ):
        self.project_root = (
            Path(project_root).resolve()
            if project_root
            else Path(__file__).resolve().parent.parent
        )
        self._sheets_module = sheets_module

    def _service(
        self,
    ):
        if self._sheets_module is not None:
            return self._sheets_module

        root = str(
            self.project_root
        )

        if root not in sys.path:
            sys.path.insert(
                0,
                root,
            )

        try:
            import sheets_service
        except Exception as error:
            raise LeadPersistenceAdapterError(
                "Could not import existing sheets_service.py."
            ) from error

        self._sheets_module = sheets_service
        return self._sheets_module

    def build_legacy_session(
        self,
        context: ConversationContext,
        quote_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        quote = context.quote
        lifecycle = context.lifecycle

        return {
            "sender_id":
                context.metadata.get(
                    "sender_id",
                    "",
                ),
            "active_lead_id":
                lifecycle.active_lead_id,
            "service":
                quote.service
                or "",
            "package":
                quote.package
                or "",
            "coverage_type":
                quote.coverage_type
                or "",
            "travel_required":
                quote.travel_required
                or "",
            "duration_hours":
                quote.duration_hours
                if quote.duration_hours is not None
                else "",
            "event_date":
                quote.event_date
                or "",
            "location":
                quote.location
                or "",
            "customer_email":
                context.customer.email,
            "customer_phone":
                context.customer.phone,
            "callback_preference":
                context.customer.callback_preference,
            "quote_data":
                quote_data
                or lifecycle.quote_data
                or {},
            "lead_data":
                lifecycle.lead_data
                or {},
            "handoff_requested":
                "Yes"
                if lifecycle.handoff_requested
                else "",
            "handoff_requested_at":
                lifecycle.handoff_requested_at,
            "handoff_status":
                lifecycle.handoff_status,
            "callback_request_sent":
                lifecycle.callback_request_sent,
            "status":
                context.state.value,
        }

    def persist_quote(
        self,
        *,
        context: ConversationContext,
        quote_data: dict[str, Any],
    ) -> LeadPersistenceResult:
        service = self._service()

        session = self.build_legacy_session(
            context,
            quote_data,
        )

        existing_lead_id = (
            context.lifecycle.active_lead_id
        )

        try:
            if existing_lead_id:
                updated = service.update_lead(
                    lead_id=existing_lead_id,
                    updates=self._quote_updates(
                        context,
                        quote_data,
                    ),
                )

                lead = (
                    updated
                    or {
                        "lead_id":
                            existing_lead_id,
                    }
                )

                created_new = False

            else:
                lead = service.save_completed_lead(
                    session=session,
                    quote_data=quote_data,
                )

                created_new = True

        except Exception as error:
            raise LeadPersistenceAdapterError(
                "Could not persist completed quote to Leads."
            ) from error

        lead_id = str(
            lead.get(
                "lead_id",
                "",
            )
        ).strip()

        context.lifecycle.active_lead_id = (
            lead_id
        )
        context.lifecycle.lead_data = dict(
            lead
        )
        context.lifecycle.quote_data = dict(
            quote_data
        )
        context.lifecycle.quote_persisted = True

        return LeadPersistenceResult(
            lead=dict(
                lead
            ),
            created_new=created_new,
        )

    def ensure_handoff_lead(
        self,
        *,
        context: ConversationContext,
        status: str = "HUMAN_HANDOFF",
    ) -> dict[str, Any]:
        """
        Ensure there is a permanent Leads row even when handoff occurs before
        a quote is complete.
        """

        if context.lifecycle.active_lead_id:
            return (
                context.lifecycle.lead_data
                or {
                    "lead_id":
                        context.lifecycle.active_lead_id,
                }
            )

        session = self.build_legacy_session(
            context,
            context.lifecycle.quote_data,
        )

        try:
            lead = self._service().save_completed_lead(
                session=session,
                quote_data={
                    **(
                        context.lifecycle.quote_data
                        or {}
                    ),
                    "status":
                        status,
                    "human_handoff":
                        True,
                },
            )
        except Exception as error:
            raise LeadPersistenceAdapterError(
                "Could not create handoff lead."
            ) from error

        context.lifecycle.active_lead_id = str(
            lead.get(
                "lead_id",
                "",
            )
        )
        context.lifecycle.lead_data = dict(
            lead
        )

        return dict(
            lead
        )

    def update_status(
        self,
        *,
        context: ConversationContext,
        status: str,
        extra_updates: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        lead_id = (
            context.lifecycle.active_lead_id
        )

        if not lead_id:
            return None

        updates = {
            "status":
                status,
        }

        if extra_updates:
            updates.update(
                extra_updates
            )

        try:
            updated = self._service().update_lead(
                lead_id=lead_id,
                updates=updates,
            )
        except Exception as error:
            raise LeadPersistenceAdapterError(
                "Could not update lead status."
            ) from error

        if updated:
            context.lifecycle.lead_data = dict(
                updated
            )

        return updated

    def _quote_updates(
        self,
        context: ConversationContext,
        quote_data: dict[str, Any],
    ) -> dict[str, Any]:
        quote = context.quote

        return {
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
            "base_price":
                quote_data.get(
                    "base_price",
                    "",
                ),
            "extra_hours":
                quote_data.get(
                    "extra_hours",
                    "",
                ),
            "extra_hour_rate":
                quote_data.get(
                    "extra_hour_rate",
                    "",
                ),
            "travel_fee":
                quote_data.get(
                    "travel_fee",
                    "",
                ),
            "quote_total":
                quote_data.get(
                    "quote_total",
                    "",
                ),
            "status":
                quote_data.get(
                    "status",
                    "QUOTE_READY",
                ),
            "human_handoff":
                quote_data.get(
                    "human_handoff",
                    False,
                ),
        }
