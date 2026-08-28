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

        deterministic_answer = self._build_package_answer_if_applicable(
            context=context,
            question_text=question_text,
            question_type=question_type,
            customer_language=customer_language,
        )

        if deterministic_answer is not None:
            answer = deterministic_answer
        else:
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

        deterministic_answer = self._build_package_answer_if_applicable(
            context=context,
            question_text=question_text,
            question_type=question_type,
            customer_language=customer_language,
        )

        if deterministic_answer is not None:
            answer = deterministic_answer
        else:
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

    def _build_package_answer_if_applicable(
        self,
        *,
        context: ConversationContext,
        question_text: str,
        question_type: str | None,
        customer_language: str,
    ) -> BusinessAnswer | None:
        """Return exact package facts from Sheets when service is known."""

        service = str(context.quote.service or "").strip()
        if not service:
            return None

        normalized_type = str(question_type or "").upper()
        normalized_text = str(question_text or "").casefold()

        looks_package_related = (
            normalized_type in self.PACKAGE_QUESTION_TYPES
            or "package" in normalized_text
            or "basic" in normalized_text
            or "premium" in normalized_text
        )

        if not looks_package_related:
            return None

        knowledge = self.answer_service.knowledge_adapter
        package_names = self.orchestrator.packages_by_service.get(
            service,
            [],
        )

        rows = []
        for package_name in package_names:
            pricing = knowledge.get_pricing(service, package_name)
            if pricing:
                rows.append((package_name, pricing))

        if not rows:
            return None

        lines = [
            f"For our {service} packages, here are the confirmed details:",
            "",
        ]

        for package_name, pricing in rows:
            included = self._display_number(pricing.get("included_hours"))
            photo = self._display_money(pricing.get("photography_price"))
            video = self._display_money(pricing.get("videography_price"))
            both = self._display_money(pricing.get("both_price"))
            extra = self._display_money(pricing.get("extra_hour_rate"))

            lines.extend([
                f"{package_name}:",
                f"- Up to {included} hours of coverage",
                f"- Photography: £{photo}",
                f"- Videography: £{video}",
                f"- Both: £{both}",
                f"- Extra hours: £{extra} per hour",
                "",
            ])

        lines.append(
            "You can choose either package based on the coverage time and option you need."
        )

        return BusinessAnswer(
            answer_found=True,
            answer_text="\n".join(lines).strip(),
            should_offer_human=False,
            language=customer_language or "English",
        )

    def _display_money(self, value) -> str:
        number = float(str(value or 0).replace("£", "").replace(",", ""))
        if number.is_integer():
            return str(int(number))
        return f"{number:.2f}"

    def _display_number(self, value) -> str:
        number = float(value or 0)
        if number.is_integer():
            return str(int(number))
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
