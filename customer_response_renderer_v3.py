from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from business_answer_service_v3 import BusinessAnswer
from response_plan import ResponseAction, ResponsePlan


@dataclass(frozen=True)
class ButtonSpec:
    label: str
    payload: str


@dataclass(frozen=True)
class RenderedMessage:
    text: str
    buttons: list[ButtonSpec] = field(
        default_factory=list
    )
    metadata: dict[str, Any] = field(
        default_factory=dict
    )


class CustomerResponseRendererV3:
    STATUS_FIELD_ORDER = (
        "service",
        "package",
        "coverage_type",
        "travel_required",
        "duration_hours",
        "event_date",
        "location",
    )

    FIELD_LABELS = {
        "service": "service",
        "package": "package",
        "coverage_type": "coverage",
        "travel_required": "travel requirement",
        "duration_hours": "coverage duration",
        "event_date": "event date",
        "location": "event location",
    }

    FIELD_PROMPTS = {
        "service":
            "What type of service are you looking for?",
        "package":
            "Which package would you like to go with: Basic or Premium?",
        "coverage_type":
            "Would you like Photography, Videography, or Both?",
        "travel_required":
            "Will travel be required for this booking?",
        "duration_hours":
            "How many hours of coverage would you like?",
        "event_date":
            "What is the event date?",
        "location":
            "What is the event location?",
    }

    RESUME_PROMPTS = {
        "service":
            "Coming back to your quote, what type of service would you like?",
        "package":
            "Coming back to your quote, would you like Basic or Premium?",
        "coverage_type":
            "Coming back to your quote, would you like Photography, Videography, or Both?",
        "travel_required":
            "Coming back to your quote, will travel be required?",
        "duration_hours":
            "Coming back to your quote, how many hours of coverage would you like?",
        "event_date":
            "Coming back to your quote, what is the event date?",
        "location":
            "Coming back to your quote, what is the event location?",
    }

    def render_plan(
        self,
        plan: ResponsePlan,
    ) -> RenderedMessage:
        action = plan.action

        if action == ResponseAction.WELCOME:
            return RenderedMessage(
                text=(
                    "Hi! How can we help you today?"
                ),
                buttons=[
                    ButtonSpec(
                        label="Get a Quote",
                        payload="GET_QUOTE",
                    ),
                    ButtonSpec(
                        label="Speak to Team",
                        payload="SPEAK_TO_TEAM",
                    ),
                ],
            )

        if action == ResponseAction.STARTED_NEW_QUOTE:
            return RenderedMessage(
                text=self.FIELD_PROMPTS.get(
                    plan.next_field,
                    "Tell us what you need for your quote.",
                ),
                buttons=self._buttons_for_plan(
                    plan
                ),
            )

        if action == ResponseAction.ANSWER_STATUS:
            summary = self._status_summary(
                plan
            )

            prompt = self.FIELD_PROMPTS.get(
                plan.next_field
            )

            text = (
                f"{summary} {prompt}"
                if prompt
                else summary
            )

            return RenderedMessage(
                text=text,
                buttons=self._buttons_for_plan(
                    plan
                ),
            )

        if action == ResponseAction.ASK_FIELD:
            prompt = self.FIELD_PROMPTS.get(
                plan.next_field,
                "Please provide the next detail for your quote.",
            )

            rejected_value = plan.metadata.get(
                "rejected_value"
            )

            if rejected_value is not None:
                rejected_field = (
                    plan.metadata.get(
                        "rejected_field"
                    )
                    or plan.next_field
                )

                allowed = ", ".join(
                    plan.metadata.get(
                        "rejected_options"
                    )
                    or plan.options
                )

                text = self._rejection_text(
                    field_name=rejected_field,
                    value=rejected_value,
                    allowed=allowed,
                    fallback=prompt,
                )

                # A rejected change targets a field the conversation is not
                # currently asking for. Say why it was rejected, then repeat
                # the question the customer still needs to answer.
                if (
                    plan.next_field
                    and rejected_field != plan.next_field
                ):
                    text = f"{text} {prompt}"

                return RenderedMessage(
                    text=text,
                    buttons=self._buttons_for_plan(
                        plan
                    ),
                )

            confirmation = self._change_confirmation(
                plan
            )

            if confirmation:
                prompt = f"{confirmation} {prompt}"

            return RenderedMessage(
                text=prompt,
                buttons=self._buttons_for_plan(
                    plan
                ),
            )

        if action == ResponseAction.RESUME_FIELD:
            return RenderedMessage(
                text=self.RESUME_PROMPTS.get(
                    plan.next_field,
                    "Coming back to your quote, please provide the next detail.",
                ),
                buttons=self._buttons_for_plan(
                    plan
                ),
            )

        if action in {
            ResponseAction.ASK_PACKAGE_RECONFIRMATION,
            ResponseAction.WAIT_PACKAGE_RECONFIRMATION,
        }:
            current = (
                plan.current_package
                or "your current package"
            )

            return RenderedMessage(
                text=(
                    f"You currently have {current} selected. "
                    f"Would you like to continue with {current} "
                    f"or switch to the other package?"
                ),
                buttons=self._package_reconfirmation_buttons(
                    current
                ),
            )

        if action == ResponseAction.REVIEW_DEFERRED_FIELDS:
            fields = ", ".join(
                plan.deferred_fields
            )

            return RenderedMessage(
                text=(
                    "There are a few details we still need to confirm"
                    + (
                        f": {fields}. "
                        if fields
                        else ". "
                    )
                    + "Would you like to confirm them now?"
                )
            )

        if action == ResponseAction.ASK_EMAIL_CONFIRMATION:
            return RenderedMessage(
                text=(
                    "Would you like a copy of your quote sent to your email?"
                ),
                buttons=[
                    ButtonSpec(
                        label="Yes",
                        payload="EMAIL_YES",
                    ),
                    ButtonSpec(
                        label="No",
                        payload="EMAIL_NO",
                    ),
                ],
            )

        if action == ResponseAction.ASK_EMAIL_ADDRESS:
            return RenderedMessage(
                text=(
                    "Please enter the email address where you would like us "
                    "to send your quote."
                )
            )

        if action == ResponseAction.INVALID_EMAIL:
            return RenderedMessage(
                text=(
                    "That email address does not look valid. "
                    "Please enter it again."
                )
            )

        if action == ResponseAction.EMAIL_SENT:
            return RenderedMessage(
                text=(
                    "Your quote has been sent to your email."
                )
            )

        if action == ResponseAction.EMAIL_FAILED:
            return RenderedMessage(
                text=(
                    "We could not send the email right now, but your quote "
                    "is still available here."
                )
            )

        if action == ResponseAction.POST_QUOTE_OPTIONS:
            return RenderedMessage(
                text=(
                    "What would you like to do next?"
                ),
                buttons=[
                    ButtonSpec(
                        label="Speak to Team",
                        payload="SPEAK_TO_TEAM",
                    ),
                    ButtonSpec(
                        label="Start New Quote",
                        payload="START_NEW_QUOTE",
                    ),
                    ButtonSpec(
                        label="Finish",
                        payload="FINISH",
                    ),
                ],
            )

        if action == ResponseAction.HANDOFF_OPTIONS:
            office_open = bool(
                plan.metadata.get(
                    "office_open",
                    False,
                )
            )
            business_phone = str(
                plan.metadata.get(
                    "business_phone",
                    "",
                )
                or ""
            ).strip()
            already_requested = bool(
                plan.metadata.get(
                    "already_requested",
                    False,
                )
            )

            if already_requested:
                message = (
                    "Your enquiry is already with our team, so no extra "
                    "confirmation is needed. If you'd like a callback, use "
                    "Request Callback below."
                )
            elif office_open and business_phone:
                message = (
                    "I've shared your enquiry with our team. Our team is "
                    "available from 9:00 AM to 5:00 PM UK time. "
                    f"You can call us now on {business_phone}. "
                    "If the team is with another client or on a shoot, "
                    "you can request a callback."
                )
            elif office_open:
                message = (
                    "I've shared your enquiry with our team. Our team is "
                    "available from 9:00 AM to 5:00 PM UK time. "
                    "If you'd prefer a call, use Request Callback below."
                )
            else:
                message = (
                    "I've shared your enquiry with our team. We're currently "
                    "outside office hours, so it has been marked for priority "
                    "follow-up during the next available office hours. "
                    "You can also request a callback below."
                )

            return RenderedMessage(
                text=message,
                buttons=[
                    ButtonSpec(
                        label="Request Callback",
                        payload="REQUEST_CALLBACK",
                    ),
                    ButtonSpec(
                        label="Start New Quote",
                        payload="START_NEW_QUOTE",
                    ),
                    ButtonSpec(
                        label="Finish",
                        payload="FINISH",
                    ),
                ],
            )

        if action == ResponseAction.ASK_CALLBACK_PHONE:
            return RenderedMessage(
                text=(
                    "Please enter the phone number you would like us to call."
                )
            )

        if action == ResponseAction.INVALID_PHONE:
            return RenderedMessage(
                text=(
                    "That phone number does not look valid. Please enter a "
                    "valid phone number including the area or country code."
                )
            )

        if action == ResponseAction.ASK_CALLBACK_PREFERENCE:
            return RenderedMessage(
                text=(
                    "When would you prefer us to call you?"
                ),
                buttons=[
                    ButtonSpec(
                        label="ASAP",
                        payload="CALLBACK_ASAP",
                    ),
                    ButtonSpec(
                        label="Morning",
                        payload="CALLBACK_MORNING",
                    ),
                    ButtonSpec(
                        label="Afternoon",
                        payload="CALLBACK_AFTERNOON",
                    ),
                ],
            )

        if action == ResponseAction.CALLBACK_RECORDED:
            office_open = bool(
                plan.metadata.get(
                    "office_open",
                    False,
                )
            )

            if office_open:
                message = (
                    "Your callback request has been sent to the team as a "
                    "priority. If the team is currently on a shoot or with "
                    "another client, they will call you as soon as they are "
                    "available during office hours."
                )
            else:
                message = (
                    "Your callback request has been saved as a priority. "
                    "The team will contact you during the next available "
                    "office hours."
                )

            return RenderedMessage(
                text=message,
                buttons=[
                    ButtonSpec(
                        label="Start New Quote",
                        payload="START_NEW_QUOTE",
                    ),
                    ButtonSpec(
                        label="Finish",
                        payload="FINISH",
                    ),
                ],
            )

        if action == ResponseAction.CALLBACK_ALREADY_RECORDED:
            return RenderedMessage(
                text=(
                    "Your callback request is already recorded. There is no "
                    "need to submit it again. Our team will follow up using "
                    "the phone number and preference you provided."
                ),
                buttons=[
                    ButtonSpec(
                        label="Start New Quote",
                        payload="START_NEW_QUOTE",
                    ),
                    ButtonSpec(
                        label="Finish",
                        payload="FINISH",
                    ),
                ],
            )

        if action == ResponseAction.PAUSED:
            return RenderedMessage(
                text=(
                    "No problem. Take your time and reply when you're ready."
                )
            )

        if action == ResponseAction.CLARIFY:
            return RenderedMessage(
                text=(
                    "Could you clarify what you'd like to do next?"
                )
            )

        if action == ResponseAction.FINISHED:
            return RenderedMessage(
                text=(
                    "Thanks for getting in touch. If you need anything else, "
                    "you can start a new quote anytime."
                )
            )

        if action in {
            ResponseAction.ANSWER_BUSINESS_QUESTION,
            ResponseAction.ANSWER_PACKAGE_RECONSIDERATION,
        }:
            raise ValueError(
                "Business-answer plans must be rendered with "
                "render_business_answer()."
            )

        if action == ResponseAction.QUOTE_READY:
            raise ValueError(
                "QUOTE_READY must be completed through quote lifecycle."
            )

        if action == ResponseAction.SEND_QUOTE_EMAIL:
            raise ValueError(
                "SEND_QUOTE_EMAIL must be completed through email service."
            )

        if action in {
            ResponseAction.PROCESS_HANDOFF_REQUEST,
            ResponseAction.START_CALLBACK_REQUEST,
            ResponseAction.PROCESS_CALLBACK_REQUEST,
        }:
            raise ValueError(
                f"{action.value} must be completed through handoff service."
            )

        raise ValueError(
            f"Unsupported response action: {action.value}"
        )

    def render_business_answer(
        self,
        *,
        answer: BusinessAnswer,
        follow_up: ResponsePlan,
    ) -> list[RenderedMessage]:
        messages: list[
            RenderedMessage
        ] = []

        if (
            answer.answer_found
            and answer.answer_text
        ):
            messages.append(
                RenderedMessage(
                    text=self._sanitize(
                        answer.answer_text
                    )
                )
            )
        else:
            messages.append(
                RenderedMessage(
                    text=(
                        "I don't have confirmed information about that at "
                        "the moment. Would you like me to connect you with "
                        "a team member?"
                    ),
                    buttons=(
                        [
                            ButtonSpec(
                                label="Speak to Team",
                                payload="SPEAK_TO_TEAM",
                            )
                        ]
                        if answer.should_offer_human
                        else []
                    ),
                )
            )

        messages.append(
            self.render_plan(
                follow_up
            )
        )

        return messages

    def render_quote(
        self,
        quote: dict[str, Any],
    ) -> RenderedMessage:
        total = quote.get(
            "quote_total"
        )

        lines = [
            "Here is your quote:",
            "",
            f"Service: {quote.get('service')}",
            f"Package: {quote.get('package')}",
            f"Coverage: {quote.get('coverage_type')}",
            f"Duration: {self._fmt_number(quote.get('duration_hours'))} hours",
            f"Base price: £{self._fmt_money(quote.get('base_price'))}",
        ]

        extra_hours = (
            quote.get(
                "extra_hours",
                0,
            )
            or 0
        )

        extra_rate = (
            quote.get(
                "extra_hour_rate",
                0,
            )
            or 0
        )

        extra_cost = (
            quote.get(
                "extra_hours_cost",
                0,
            )
            or 0
        )

        if float(
            extra_hours
        ) > 0:
            lines.append(
                "Extra hours: "
                f"{self._fmt_number(extra_hours)} × "
                f"£{self._fmt_money(extra_rate)} = "
                f"£{self._fmt_money(extra_cost)}"
            )

        travel_fee = (
            quote.get(
                "travel_fee",
                0,
            )
            or 0
        )

        if float(
            travel_fee
        ) > 0:
            lines.append(
                f"Travel: £{self._fmt_money(travel_fee)}"
            )

        lines.extend(
            [
                "",
                f"Total: £{self._fmt_money(total)}",
            ]
        )

        return RenderedMessage(
            text="\n".join(
                lines
            )
        )

    def _status_summary(
        self,
        plan,
    ) -> str:
        """
        Answer a question about the quote from what Python already holds.

        The customer is asking what is recorded, not asking to change it,
        so nothing here reopens a decision.
        """

        quote = plan.metadata.get(
            "quote_summary"
        ) or {}

        parts = []

        for field_name in self.STATUS_FIELD_ORDER:
            value = quote.get(
                field_name
            )

            if value in (None, ""):
                continue

            label = self.FIELD_LABELS.get(
                field_name,
                field_name.replace("_", " "),
            )

            parts.append(
                f"{label}: {value}"
            )

        if not parts:
            return (
                "We have not recorded any quote details yet."
            )

        return (
            "Here is what I have on your quote so far - "
            + ", ".join(parts)
            + "."
        )

    def _rejection_text(
        self,
        *,
        field_name: str | None,
        value,
        allowed: str,
        fallback: str,
    ) -> str:
        if field_name == "package":
            return (
                f"{value} is not an available package. "
                f"Please choose {allowed}."
            )

        if field_name == "service":
            return (
                f"{value} is not an available service. "
                f"Please choose {allowed}."
            )

        if field_name == "coverage_type":
            return (
                f"{value} is not a valid coverage option. "
                f"Please choose {allowed}."
            )

        if field_name == "travel_required":
            return (
                "Please answer Yes or No for whether "
                "travel is required."
            )

        return fallback

    def _change_confirmation(
        self,
        plan,
    ) -> str | None:
        """
        Tell the customer what happened to the change they asked for.

        A no-op change is still an answer. Repeating the next question on
        its own reads as the bot ignoring them.
        """

        changed_field = plan.metadata.get(
            "changed_field"
        )

        if not changed_field:
            return None

        label = self.FIELD_LABELS.get(
            changed_field,
            str(changed_field).replace("_", " "),
        )

        value = plan.metadata.get(
            "changed_value"
        )

        if value in (None, ""):
            return None

        if plan.metadata.get(
            "change_applied"
        ):
            return (
                f"Done, your {label} is now {value}."
            )

        return (
            f"Your {label} is already {value}, "
            f"so nothing has changed."
        )

    def _buttons_for_plan(
        self,
        plan: ResponsePlan,
    ) -> list[ButtonSpec]:
        field_name = (
            plan.next_field
        )

        payload_prefix = {
            "service": "SERVICE",
            "package": "PACKAGE",
            "coverage_type": "COVERAGE",
            "travel_required": "TRAVEL",
        }.get(
            field_name
        )

        if not payload_prefix:
            return []

        return [
            ButtonSpec(
                label=str(
                    option
                ),
                payload=(
                    f"{payload_prefix}_"
                    f"{str(option).upper().replace(' ', '_')}"
                ),
            )
            for option in plan.options
        ]

    def _package_reconfirmation_buttons(
        self,
        current_package: str,
    ) -> list[ButtonSpec]:
        other = (
            "Premium"
            if current_package.lower()
            == "basic"
            else "Basic"
        )

        return [
            ButtonSpec(
                label=f"Keep {current_package}",
                payload="KEEP_CURRENT_PACKAGE",
            ),
            ButtonSpec(
                label=f"Switch to {other}",
                payload=f"SWITCH_PACKAGE_{other.upper()}",
            ),
        ]

    def _sanitize(
        self,
        text: str,
    ) -> str:
        cleaned = str(
            text
        ).replace(
            "**",
            "",
        ).strip()

        cleaned = cleaned.replace(
            "testing",
            "",
        ).replace(
            "Testing",
            "",
        )

        return cleaned

    def _fmt_money(
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

        return f"{number:.2f}"

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
