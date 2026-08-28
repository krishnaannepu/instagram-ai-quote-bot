from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any

from conversation_events import ConversationEvent
from conversation_models import ConversationContext, FlowState
from response_plan import ResponsePlan
from semantic_contract import SemanticInterpretation


def _utc_timestamp() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


def _safe_state(
    state,
) -> str:
    if isinstance(state, FlowState):
        return state.value

    return str(state)


def build_turn_log(
    *,
    context_before: ConversationContext,
    context_after: ConversationContext,
    customer_message: str,
    interpretation: SemanticInterpretation | None,
    event: ConversationEvent | None,
    response_plan: ResponsePlan | None,
    error: str | None = None,
) -> dict[str, Any]:
    """
    Build one structured turn record.

    This does not persist anywhere yet. A later repository/logger can write
    the returned dictionary to Cloud Logging, Firestore, or another sink.
    """

    return {
        "timestamp":
            _utc_timestamp(),

        "customer_message":
            customer_message,

        "before": {
            "state":
                _safe_state(
                    context_before.state
                ),
            "quote":
                context_before.quote.as_dict(),
            "resume_stack": [
                _safe_state(state)
                for state in context_before.resume_stack
            ],
            "deferred_fields":
                list(
                    context_before.deferred_fields
                ),
        },

        "interpretation": (
            {
                "action":
                    interpretation.action.value,
                "field_name":
                    interpretation.field_name,
                "value":
                    interpretation.value,
                "question_type":
                    interpretation.question_type,
                "question_text":
                    interpretation.question_text,
                "confidence":
                    interpretation.confidence,
                "language":
                    interpretation.language,
            }
            if interpretation
            else None
        ),

        "event": (
            {
                "type":
                    event.type.value,
                "field":
                    event.field,
                "value":
                    event.value,
                "question_type":
                    event.question_type,
                "question_text":
                    event.question_text,
                "source":
                    event.metadata.get(
                        "source"
                    ),
            }
            if event
            else None
        ),

        "after": {
            "state":
                _safe_state(
                    context_after.state
                ),
            "quote":
                context_after.quote.as_dict(),
            "resume_stack": [
                _safe_state(state)
                for state in context_after.resume_stack
            ],
            "deferred_fields":
                list(
                    context_after.deferred_fields
                ),
        },

        "response_plan": (
            {
                "action":
                    response_plan.action.value,
                "state":
                    response_plan.state.value,
                "next_field":
                    response_plan.next_field,
                "options":
                    list(
                        response_plan.options
                    ),
                "current_package":
                    response_plan.current_package,
                "deferred_fields":
                    list(
                        response_plan.deferred_fields
                    ),
            }
            if response_plan
            else None
        ),

        "error":
            error,
    }


def format_turn_log(
    log_record: dict[str, Any],
) -> str:
    """
    Human-readable structured JSON for local debugging and Cloud Logging.
    """

    return json.dumps(
        log_record,
        ensure_ascii=False,
        indent=2,
        default=str,
    )
