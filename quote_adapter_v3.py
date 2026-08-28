from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from conversation_models import (
    ConversationContext,
    FlowState,
)


class QuoteAdapterError(RuntimeError):
    pass


class QuoteAdapterV3:
    """
    Thin adapter over the existing deterministic quote_service.py.

    Gemini is never called here.
    """

    def __init__(
        self,
        *,
        project_root: Path | None = None,
        quote_module=None,
    ):
        self.project_root = (
            Path(project_root).resolve()
            if project_root
            else Path(__file__).resolve().parent.parent
        )
        self._quote_module = quote_module

    def _service(self):
        if self._quote_module is not None:
            return self._quote_module

        project_root_text = str(
            self.project_root
        )

        if project_root_text not in sys.path:
            sys.path.insert(
                0,
                project_root_text,
            )

        try:
            import quote_service
        except Exception as error:
            raise QuoteAdapterError(
                "Could not import existing quote_service.py "
                "from the project root."
            ) from error

        self._quote_module = quote_service
        return self._quote_module

    def build_session_dict(
        self,
        context: ConversationContext,
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
        }

    def calculate(
        self,
        context: ConversationContext,
    ) -> dict[str, Any]:
        if (
            context.state
            != FlowState.QUOTE_READY
        ):
            raise QuoteAdapterError(
                "Final quote calculation requires QUOTE_READY state."
            )

        required_fields = [
            "service",
            "package",
            "coverage_type",
            "travel_required",
            "duration_hours",
            "event_date",
            "location",
        ]

        missing = [
            field_name
            for field_name in required_fields
            if context.quote.get(
                field_name
            )
            in {
                None,
                "",
            }
        ]

        if missing:
            raise QuoteAdapterError(
                f"Cannot calculate quote; missing fields: "
                f"{missing}"
            )

        service = self._service()

        try:
            quote = service.calculate_quote(
                session=self.build_session_dict(
                    context
                )
            )
        except Exception as error:
            raise QuoteAdapterError(
                "Deterministic quote calculation failed."
            ) from error

        if not isinstance(
            quote,
            dict,
        ):
            raise QuoteAdapterError(
                "quote_service.calculate_quote() "
                "did not return a dictionary."
            )

        context.quote_version += 1
        context.quote_is_stale = False

        return quote

    def calculate_for_package(
        self,
        context: ConversationContext,
        package_name: str,
        *,
        assume_no_travel_if_unknown: bool = False,
    ) -> dict[str, Any]:
        """
        Calculate a comparison quote without mutating the live context.

        Used only when enough quote information is already known.
        """

        from copy import deepcopy

        comparison_context = deepcopy(
            context
        )

        comparison_context.quote.package = (
            package_name
        )

        if (
            not comparison_context
            .quote
            .travel_required
            and assume_no_travel_if_unknown
        ):
            comparison_context.quote.travel_required = (
                "No"
            )

        comparison_context.state = (
            FlowState.QUOTE_READY
        )

        return self.calculate(
            comparison_context
        )
