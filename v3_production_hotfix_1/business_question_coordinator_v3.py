from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from business_answer_service_v3 import (
    BusinessAnswer,
    BusinessAnswerServiceV3,
)
from conversation_events import ConversationEvent, EventType
from conversation_models import ConversationContext, FlowState
from conversation_orchestrator import ConversationOrchestrator
from quote_adapter_v3 import QuoteAdapterV3
from response_plan import ResponseAction, ResponsePlan


@dataclass
class BusinessQuestionResolution:
    answer: BusinessAnswer
    resume_plan: ResponsePlan
    calculated_context: dict[str, Any]


class BusinessQuestionCoordinatorV3:
    PACKAGE_QUESTION_TYPES = {
        "PACKAGE_COMPARISON",
        "PACKAGE_PRICING",
        "PACKAGE_PRICING_COMPARISON",
        "PACKAGE_COMPARISON_WITH_PRICING",
        "PACKAGE_RECOMMENDATION",
    }

    def __init__(
        self,
        *,
        orchestrator: ConversationOrchestrator,
        answer_service: BusinessAnswerServiceV3,
        quote_adapter: QuoteAdapterV3 | None = None,
    ):
        self.orchestrator = orchestrator
        self.answer_service = answer_service
        self.quote_adapter = quote_adapter

    def resolve(
        self,
        *,
        context: ConversationContext,
        question_text: str,
        question_type: str | None,
        customer_language: str = "English",
    ) -> BusinessQuestionResolution:
        if context.state != FlowState.BUSINESS_INTERRUPT:
            raise ValueError(
                "Normal business question resolution requires "
                "BUSINESS_INTERRUPT state."
            )

        calculated_context = self._build_calculated_context(
            context=context,
            question_type=question_type,
        )

        answer = self._try_deterministic_package_answer(
            context=context,
            question_text=question_text,
            question_type=question_type,
            customer_language=customer_language,
        )

        if answer is None:
            answer = self.answer_service.answer(
                context=context,
                question_text=question_text,
                question_type=question_type,
                customer_language=customer_language,
                calculated_context=calculated_context,
            )

        event = ConversationEvent(
            type=EventType.BUSINESS_QUESTION_RESOLVED,
            metadata={
                "source": "business_question_coordinator",
            },
        )

        transition = self.orchestrator.state_machine.handle(
            context,
            event,
        )

        resume_plan = self.orchestrator._plan_response(
            context=context,
            interpretation=None,
            event=event,
            transition=transition,
        )

        return BusinessQuestionResolution(
            answer=answer,
            resume_plan=resume_plan,
            calculated_context=calculated_context,
        )

    def resolve_package_reconsideration(
        self,
        *,
        context: ConversationContext,
        question_text: str,
        question_type: str | None,
        customer_language: str = "English",
    ) -> BusinessQuestionResolution:
        """
        The package reconsideration question has already transitioned Python
        into PACKAGE_RECONFIRMATION.

        Answer the comparison/pricing question without leaving that state,
        then return an explicit keep/switch follow-up plan.
        """

        if context.state != FlowState.PACKAGE_RECONFIRMATION:
            raise ValueError(
                "Package reconsideration answer requires "
                "PACKAGE_RECONFIRMATION state."
            )

        calculated_context = self._build_calculated_context(
            context=context,
            question_type=question_type,
        )

        answer = self._try_deterministic_package_answer(
            context=context,
            question_text=question_text,
            question_type=question_type,
            customer_language=customer_language,
        )

        if answer is None:
            answer = self.answer_service.answer(
                context=context,
                question_text=question_text,
                question_type=question_type,
                customer_language=customer_language,
                calculated_context=calculated_context,
            )

        follow_up = self.orchestrator.package_reconfirmation_plan(
            context=context,
            language=customer_language,
        )

        return BusinessQuestionResolution(
            answer=answer,
            resume_plan=follow_up,
            calculated_context=calculated_context,
        )

    def _try_deterministic_package_answer(
        self,
        *,
        context: ConversationContext,
        question_text: str,
        question_type: str | None,
        customer_language: str,
    ) -> BusinessAnswer | None:
        """
        Package facts are business data, not generative content.

        If the service is already known and the customer is asking about one
        or more packages, build the answer directly from the approved Sheets
        catalogue. This prevents the model from asking for a service that
        Python already knows or from replacing exact package facts with a
        generic explanation.
        """

        service_name = str(
            context.quote.service
            or ""
        ).strip()

        if not service_name:
            return None

        packages = list(
            self.orchestrator
            .packages_by_service
            .get(
                service_name,
                [],
            )
        )

        if not packages:
            return None

        question_lower = str(
            question_text
            or ""
        ).casefold()

        mentioned_packages = [
            package_name
            for package_name in packages
            if package_name.casefold()
            in question_lower
        ]

        is_package_question = (
            question_type
            in self.PACKAGE_QUESTION_TYPES
            or bool(
                mentioned_packages
            )
        )

        if not is_package_question:
            return None

        packages_to_show = (
            mentioned_packages
            if mentioned_packages
            else packages
        )

        # A comparison naming more than one package should always show all
        # named packages in catalogue order.
        packages_to_show = [
            package_name
            for package_name in packages
            if package_name
            in packages_to_show
        ]

        sections: list[str] = []

        for package_name in packages_to_show:
            pricing = (
                self.answer_service
                .knowledge_adapter
                .get_pricing(
                    service_name,
                    package_name,
                )
            )

            package_info = (
                self.answer_service
                .knowledge_adapter
                .get_package(
                    service_name,
                    package_name,
                )
            )

            if not pricing:
                continue

            lines = [
                f"{package_name}:",
                (
                    "- Up to "
                    f"{self._fmt_number(pricing.get('included_hours'))} "
                    "hours of coverage"
                ),
                (
                    "- Photography: £"
                    f"{self._fmt_money(pricing.get('photography_price'))}"
                ),
                (
                    "- Videography: £"
                    f"{self._fmt_money(pricing.get('videography_price'))}"
                ),
                (
                    "- Both: £"
                    f"{self._fmt_money(pricing.get('both_price'))}"
                ),
                (
                    "- Extra hour: £"
                    f"{self._fmt_money(pricing.get('extra_hour_rate'))}"
                ),
            ]

            description = str(
                (
                    package_info
                    or {}
                ).get(
                    "description",
                    "",
                )
                or ""
            ).strip()

            if description:
                lines.append(
                    f"- {description}"
                )

            sections.append(
                "\n".join(
                    lines
                )
            )

        if not sections:
            return None

        if len(sections) > 1:
            intro = (
                f"For {service_name}, here is the exact difference between "
                + " and ".join(
                    packages_to_show
                )
                + ":"
            )
        else:
            intro = (
                f"For {service_name}, here are the approved "
                f"{packages_to_show[0]} package details:"
            )

        return BusinessAnswer(
            answer_found=True,
            answer_text=(
                intro
                + "\n\n"
                + "\n\n".join(
                    sections
                )
            ),
            should_offer_human=False,
            language=(
                customer_language
                or "English"
            ),
        )

    def _fmt_money(
        self,
        value,
    ) -> str:
        cleaned = (
            str(
                value
                if value is not None
                else "0"
            )
            .replace(
                "£",
                "",
            )
            .replace(
                ",",
                "",
            )
            .strip()
        )

        try:
            number = float(
                cleaned
                or 0
            )
        except ValueError:
            return cleaned

        if number.is_integer():
            return str(
                int(
                    number
                )
            )

        return f"{number:.2f}"

    def _fmt_number(
        self,
        value,
    ) -> str:
        cleaned = str(
            value
            if value is not None
            else "0"
        ).strip()

        try:
            number = float(
                cleaned
                or 0
            )
        except ValueError:
            return cleaned

        if number.is_integer():
            return str(
                int(
                    number
                )
            )

        return f"{number:g}"

    def _build_calculated_context(
        self,
        *,
        context: ConversationContext,
        question_type: str | None,
    ) -> dict[str, Any]:
        if (
            not self.quote_adapter
            or question_type not in self.PACKAGE_QUESTION_TYPES
        ):
            return {}

        quote = context.quote

        if (
            not quote.service
            or not quote.coverage_type
            or quote.duration_hours in {None, ""}
        ):
            return {}

        packages = self.orchestrator.packages_by_service.get(
            quote.service,
            [],
        )

        if not packages:
            return {}

        travel_known = bool(quote.travel_required)
        comparisons = []

        for package_name in packages:
            try:
                calculated = self.quote_adapter.calculate_for_package(
                    context,
                    package_name,
                    assume_no_travel_if_unknown=not travel_known,
                )
            except Exception:
                continue

            comparisons.append(
                {
                    "package": package_name,
                    "quote_total": calculated.get("quote_total"),
                    "base_price": calculated.get("base_price"),
                    "included_hours": calculated.get("included_hours"),
                    "extra_hours": calculated.get("extra_hours"),
                    "extra_hour_rate": calculated.get("extra_hour_rate"),
                    "travel_fee": calculated.get("travel_fee"),
                }
            )

        return {
            "travel_requirement_known": travel_known,
            "package_comparisons": comparisons,
        }
