from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from conversation_events import (
    ConversationEvent,
    EventType,
)
from conversation_models import (
    ConversationContext,
    FlowState,
)
from conversation_orchestrator import (
    ConversationOrchestrator,
)
from email_delivery_adapter_v3 import (
    EmailDeliveryAdapterV3,
)
from lead_persistence_adapter_v3 import (
    LeadPersistenceAdapterV3,
    LeadPersistenceResult,
)
from quote_adapter_v3 import QuoteAdapterV3
from response_plan import ResponsePlan


@dataclass
class QuoteCompletionResult:
    quote: dict[str, Any]
    lead: dict[str, Any]
    created_new_lead: bool
    next_plan: ResponsePlan


class QuoteCompletionServiceV3:
    """
    Deterministic quote completion lifecycle:

    QUOTE_READY
      -> calculate in Python
      -> persist/update Leads
      -> optional internal owner notification
      -> EMAIL_CONFIRMATION
    """

    def __init__(
        self,
        *,
        orchestrator:
            ConversationOrchestrator,
        quote_adapter:
            QuoteAdapterV3,
        lead_persistence:
            LeadPersistenceAdapterV3,
        email_delivery:
            EmailDeliveryAdapterV3 | None = None,
    ):
        self.orchestrator = (
            orchestrator
        )
        self.quote_adapter = (
            quote_adapter
        )
        self.lead_persistence = (
            lead_persistence
        )
        self.email_delivery = (
            email_delivery
        )

    def complete(
        self,
        *,
        context: ConversationContext,
    ) -> QuoteCompletionResult:
        if context.state != FlowState.QUOTE_READY:
            raise ValueError(
                "Quote completion requires QUOTE_READY state."
            )

        quote = self.quote_adapter.calculate(
            context
        )

        persistence = (
            self.lead_persistence
            .persist_quote(
                context=context,
                quote_data=quote,
            )
        )

        context.lifecycle.quote_data = dict(
            quote
        )
        context.lifecycle.lead_data = dict(
            persistence.lead
        )
        context.lifecycle.quote_persisted = True

        if (
            persistence.created_new
            and self.email_delivery
        ):
            self.email_delivery.send_new_lead_notification(
                context=context,
                quote_data=quote,
                lead_data=persistence.lead,
            )

        event = ConversationEvent(
            type=EventType.QUOTE_COMPLETED,
            metadata={
                "source":
                    "quote_completion_service",
            },
        )

        transition = (
            self.orchestrator
            .state_machine
            .handle(
                context,
                event,
            )
        )

        next_plan = (
            self.orchestrator
            ._plan_response(
                context=context,
                interpretation=None,
                event=event,
                transition=transition,
            )
        )

        return QuoteCompletionResult(
            quote=quote,
            lead=dict(
                persistence.lead
            ),
            created_new_lead=
                persistence.created_new,
            next_plan=
                next_plan,
        )
