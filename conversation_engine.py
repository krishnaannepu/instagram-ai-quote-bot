from __future__ import annotations

from typing import Any

from conversation_state import (
    FlowState,
    clear_resume_stack,
    expected_field_for_state,
    get_flow_state,
    initialize_flow_state,
    pop_resume_state,
    push_resume_state,
    state_for_field,
    transition,
)
from gemini_service import (
    CustomerMessageUnderstanding,
    answer_business_question,
    get_current_catalogue,
    interpret_expected_field_reply,
    understand_customer_message,
)
from quote_service import calculate_quote


# ------------------------------------------------------------------
# Quote Configuration
# ------------------------------------------------------------------

QUOTE_FIELDS = (
    "service",
    "package",
    "coverage_type",
    "travel_required",
    "duration_hours",
    "event_date",
    "location",
)

REQUIRED_QUOTE_FIELDS = QUOTE_FIELDS

FIELD_ORDER = {
    field_name: index
    for index, field_name in enumerate(
        QUOTE_FIELDS,
        start=1,
    )
}


# ------------------------------------------------------------------
# Basic Helpers
# ------------------------------------------------------------------

def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _has_value(value: Any) -> bool:
    if value is None:
        return False

    if isinstance(value, str):
        return bool(value.strip())

    return True


def _canonical_from_list(
    value: Any,
    allowed_values: list[str],
) -> str | None:
    cleaned = _clean_text(value)

    if not cleaned:
        return None

    for allowed in allowed_values:
        if cleaned.lower() == str(allowed).strip().lower():
            return allowed

    return None


def _language_of(result: Any, default: str = "English") -> str:
    return _clean_text(getattr(result, "language", None)) or default


# ------------------------------------------------------------------
# Dynamic Catalogue
# ------------------------------------------------------------------

def get_supported_services() -> list[str]:
    return list(
        get_current_catalogue().get(
            "supported_services",
            [],
        )
    )


def get_packages_for_service(
    service: str | None,
) -> list[str]:
    cleaned_service = _clean_text(service)

    if not cleaned_service:
        return []

    catalogue = get_current_catalogue()

    for catalogue_service, packages in (
        catalogue.get(
            "packages_by_service",
            {},
        ).items()
    ):
        if catalogue_service.lower() == cleaned_service.lower():
            return list(packages)

    return []


def get_available_options_for_field(
    field_name: str,
    session: dict,
) -> list[str]:
    if field_name == "service":
        return get_supported_services()

    if field_name == "package":
        return get_packages_for_service(
            session.get("service")
        )

    if field_name == "coverage_type":
        return [
            "Photography",
            "Videography",
            "Both",
        ]

    if field_name in {
        "travel_required",
        "deferred_review_ready",
        "email_quote_copy",
    }:
        return [
            "Yes",
            "No",
        ]

    return []


# ------------------------------------------------------------------
# Missing / Deferred Quote Fields
# ------------------------------------------------------------------

def get_missing_quote_fields(
    session: dict,
) -> list[str]:
    missing = [
        field_name
        for field_name in REQUIRED_QUOTE_FIELDS
        if not _has_value(
            session.get(field_name)
        )
    ]

    return sorted(
        missing,
        key=lambda field_name: FIELD_ORDER[field_name],
    )


def get_next_missing_quote_field(
    session: dict,
) -> str | None:
    missing = get_missing_quote_fields(session)
    return missing[0] if missing else None


def get_deferred_quote_fields(
    session: dict,
) -> list[str]:
    missing = set(
        get_missing_quote_fields(session)
    )

    deferred = session.get(
        "deferred_quote_fields",
        [],
    )

    if not isinstance(deferred, list):
        deferred = []

    return [
        field_name
        for field_name in QUOTE_FIELDS
        if field_name in missing
        and field_name in deferred
    ]


def get_next_quote_field_for_prompt(
    session: dict,
) -> str | None:
    missing = get_missing_quote_fields(session)

    if not missing:
        return None

    deferred = set(
        get_deferred_quote_fields(session)
    )

    for field_name in missing:
        if field_name not in deferred:
            return field_name

    if session.get(
        "deferred_review_active",
        False,
    ):
        return missing[0]

    return None


def quote_is_complete(session: dict) -> bool:
    return not get_missing_quote_fields(session)


# ------------------------------------------------------------------
# State Synchronisation
# ------------------------------------------------------------------

def _ensure_state(session: dict) -> str:
    state = initialize_flow_state(
        session,
        quote_fields=QUOTE_FIELDS,
        missing_fields=get_missing_quote_fields(
            session
        ),
        deferred_fields=get_deferred_quote_fields(
            session
        ),
    )

    # An explicitly started quote should not remain IDLE.
    if (
        state == FlowState.IDLE.value
        and session.get("selected_action") == "GET_QUOTE"
    ):
        next_field = (
            get_next_quote_field_for_prompt(
                session
            )
            or get_next_missing_quote_field(
                session
            )
        )

        if next_field:
            state = transition(
                session,
                state_for_field(next_field),
                "quote flow started",
            )

    return state


def _set_quote_state_from_data(
    session: dict,
    reason: str,
) -> str:
    missing = get_missing_quote_fields(session)

    if not missing:
        session["deferred_review_pending"] = False
        session["deferred_review_active"] = False
        session["status"] = "QUOTE_INPUT_COMPLETE"
        return transition(
            session,
            FlowState.QUOTE_READY,
            reason,
        )

    next_field = get_next_quote_field_for_prompt(
        session
    )

    if next_field:
        session["status"] = "ACTIVE"
        session["current_stage"] = "AI_QUOTE"
        return transition(
            session,
            state_for_field(next_field),
            reason,
        )

    session["deferred_review_pending"] = True
    session["deferred_review_active"] = False
    session["status"] = "AWAITING_DEFERRED_CONFIRMATION"
    session["current_stage"] = "AI_DEFERRED_CONFIRMATION"

    return transition(
        session,
        FlowState.DEFERRED_REVIEW_READY,
        reason,
    )


def _resume_prompt_for_state(
    session: dict,
) -> dict | None:
    state = get_flow_state(session)

    if state == FlowState.PACKAGE_RECONFIRMATION.value:
        current_package = _clean_text(
            session.get(
                "package_reconfirmation_current"
            )
            or session.get("package")
        )

        return {
            "action": "RECONFIRM_PACKAGE_SELECTION",
            "next_field": "package",
            "options": get_packages_for_service(
                session.get("service")
            ),
            "current_value": current_package,
        }

    if state == FlowState.DEFERRED_REVIEW_READY.value:
        return {
            "action": "REVIEW_DEFERRED_FIELDS",
            "deferred_fields": get_deferred_quote_fields(
                session
            ),
        }

    expected_field = expected_field_for_state(state)

    if expected_field:
        return {
            "action": "ASK_FOR_FIELD",
            "next_field": expected_field,
            "options": get_available_options_for_field(
                expected_field,
                session,
            ),
        }

    return None


# ------------------------------------------------------------------
# Quote Mutation Validation
# ------------------------------------------------------------------

def _invalidate_existing_quote(
    session: dict,
) -> None:
    session["quote_data"] = {}

    if session.get("status") in {
        "QUOTE_INPUT_COMPLETE",
        "QUOTE_GENERATED",
        "QUOTE_READY",
        "QUOTE_SENT",
        "QUOTE_EMAILED",
        "COMPLETED",
    }:
        session["status"] = "ACTIVE"


def _validate_quote_value(
    field_name: str,
    raw_value: Any,
    session: dict,
) -> Any | None:
    if raw_value is None:
        return None

    if field_name == "service":
        return _canonical_from_list(
            raw_value,
            get_supported_services(),
        )

    if field_name == "package":
        return _canonical_from_list(
            raw_value,
            get_packages_for_service(
                session.get("service")
            ),
        )

    if field_name == "coverage_type":
        return _canonical_from_list(
            raw_value,
            [
                "Photography",
                "Videography",
                "Both",
            ],
        )

    if field_name == "travel_required":
        return _canonical_from_list(
            raw_value,
            [
                "Yes",
                "No",
            ],
        )

    if field_name == "duration_hours":
        try:
            duration = float(raw_value)
        except (TypeError, ValueError):
            return None

        if duration <= 0:
            return None

        if duration.is_integer():
            return int(duration)

        return duration

    if field_name in {
        "event_date",
        "location",
        "special_requirements",
    }:
        cleaned = _clean_text(raw_value)
        return cleaned or None

    return None


def _remove_deferred_field(
    session: dict,
    field_name: str,
) -> None:
    deferred = session.get(
        "deferred_quote_fields",
        [],
    )

    if not isinstance(deferred, list):
        deferred = []

    session["deferred_quote_fields"] = [
        item
        for item in deferred
        if item != field_name
    ]


def _apply_one_field(
    session: dict,
    field_name: str,
    raw_value: Any,
) -> tuple[bool, bool]:
    """Return ``(changed, accepted)`` for one field."""

    value = _validate_quote_value(
        field_name,
        raw_value,
        session,
    )

    if value is None:
        return False, False

    old_value = session.get(field_name)

    if old_value == value:
        _remove_deferred_field(
            session,
            field_name,
        )
        return False, True

    # Service changes can invalidate the old package.
    if field_name == "service":
        old_service = _clean_text(
            session.get("service")
        )
        session["service"] = value

        if old_service.lower() != str(value).lower():
            current_package = _clean_text(
                session.get("package")
            )

            if current_package:
                valid_package = _canonical_from_list(
                    current_package,
                    get_packages_for_service(value),
                )

                if valid_package is None:
                    session["package"] = ""

    else:
        session[field_name] = value

    _remove_deferred_field(
        session,
        field_name,
    )
    _invalidate_existing_quote(session)

    return True, True


def apply_customer_understanding(
    session: dict,
    understanding: CustomerMessageUnderstanding,
) -> dict:
    """Apply only fields explicitly listed by Gemini in ``fields_to_update``.

    This restores the state-safety guarantee: contextual values repeated by
    Gemini can never silently rewrite an existing quote field.
    """

    requested_updates = list(
        getattr(
            understanding,
            "fields_to_update",
            [],
        )
        or []
    )

    changed_fields: list[str] = []
    rejected_fields: list[str] = []

    for field_name in requested_updates:
        if field_name not in {
            *QUOTE_FIELDS,
            "special_requirements",
        }:
            rejected_fields.append(field_name)
            continue

        raw_value = getattr(
            understanding,
            field_name,
            None,
        )

        changed, accepted = _apply_one_field(
            session,
            field_name,
            raw_value,
        )

        if not accepted:
            rejected_fields.append(field_name)
        elif changed:
            changed_fields.append(field_name)

    return {
        "session": session,
        "changed_fields": changed_fields,
        "rejected_fields": rejected_fields,
    }


# ------------------------------------------------------------------
# Package Price Comparison
# ------------------------------------------------------------------

def _build_package_catalogue_pricing(
    session: dict,
    requested_packages: list[str] | None = None,
) -> dict:
    service = _clean_text(session.get("service"))

    if not service:
        return {
            "answer_found": True,
            "answer_text": (
                "I can compare the package prices. "
                "Which service would you like pricing for?"
            ),
            "should_offer_human": False,
            "comparison_quotes": [],
            "comparison_mode": "NEEDS_SERVICE",
        }

    available_packages = get_packages_for_service(
        service
    )

    canonical_requested = []

    for requested in requested_packages or []:
        canonical = _canonical_from_list(
            requested,
            available_packages,
        )

        if canonical and canonical not in canonical_requested:
            canonical_requested.append(canonical)

    packages_to_compare = (
        canonical_requested
        or available_packages
    )

    blocks = []
    pricing_rows = []

    for package_name in packages_to_compare:
        package_quotes = []

        for coverage_type in [
            "Photography",
            "Videography",
            "Both",
        ]:
            comparison_session = dict(session)
            comparison_session["package"] = package_name
            comparison_session["coverage_type"] = coverage_type
            comparison_session["travel_required"] = "No"
            comparison_session["duration_hours"] = 1

            try:
                quote = calculate_quote(
                    session=comparison_session
                )
            except Exception:
                continue

            package_quotes.append(quote)
            pricing_rows.append(quote)

        if not package_quotes:
            continue

        first_quote = package_quotes[0]
        prices = {
            quote["coverage_type"]: quote["base_price"]
            for quote in package_quotes
        }

        blocks.append(
            f"{package_name}\n"
            f"Photography: £{prices['Photography']:,.2f}\n"
            f"Videography: £{prices['Videography']:,.2f}\n"
            f"Both: £{prices['Both']:,.2f}\n"
            f"Includes up to: {first_quote['included_hours']:g} hours\n"
            f"Extra hour: £{first_quote['extra_hour_rate']:,.2f}"
        )

    if not blocks:
        return {
            "answer_found": False,
            "answer_text": (
                "I don't have confirmed package pricing for that "
                "service at the moment."
            ),
            "should_offer_human": True,
            "comparison_quotes": [],
            "comparison_mode": "CATALOGUE_PRICING",
        }

    return {
        "answer_found": True,
        "answer_text": "\n\n".join(blocks),
        "should_offer_human": False,
        "comparison_quotes": pricing_rows,
        "comparison_mode": "CATALOGUE_PRICING",
    }


def _build_package_price_comparison(
    session: dict,
    requested_packages: list[str] | None = None,
) -> dict:
    # Without service, a deterministic price table cannot be selected.
    if not _has_value(session.get("service")):
        return {
            "answer_found": True,
            "answer_text": (
                "I can compare the package prices. "
                "Which service would you like the comparison for?"
            ),
            "should_offer_human": False,
            "comparison_quotes": [],
            "comparison_mode": "NEEDS_SERVICE",
        }

    # If coverage or duration is missing, show approved catalogue pricing
    # rather than hijacking quote collection to ask more comparison inputs.
    if (
        not _has_value(session.get("coverage_type"))
        or not _has_value(session.get("duration_hours"))
    ):
        return _build_package_catalogue_pricing(
            session=session,
            requested_packages=requested_packages,
        )

    service = _clean_text(session.get("service"))
    available_packages = get_packages_for_service(
        service
    )

    canonical_requested = []

    for requested in requested_packages or []:
        canonical = _canonical_from_list(
            requested,
            available_packages,
        )

        if canonical and canonical not in canonical_requested:
            canonical_requested.append(canonical)

    packages_to_compare = (
        canonical_requested
        or available_packages
    )

    travel_known = _has_value(
        session.get("travel_required")
    )

    comparison_quotes = []

    for package_name in packages_to_compare:
        comparison_session = dict(session)
        comparison_session["package"] = package_name

        if not travel_known:
            comparison_session["travel_required"] = "No"

        try:
            quote = calculate_quote(
                session=comparison_session
            )
        except Exception:
            continue

        comparison_quotes.append(quote)

    if not comparison_quotes:
        return {
            "answer_found": False,
            "answer_text": (
                "I don't have confirmed package pricing for that "
                "service at the moment."
            ),
            "should_offer_human": True,
            "comparison_quotes": [],
            "comparison_mode": "PERSONALISED_TOTALS",
        }

    blocks = []

    for quote in comparison_quotes:
        block = (
            f"{quote['package']}\n"
            f"Included coverage: {quote['included_hours']:g} hours\n"
            f"Base price: £{quote['base_price']:,.2f}\n"
            f"Extra hours: {quote['extra_hours']:g}\n"
            f"Extra hours cost: £{quote['extra_hours_cost']:,.2f}\n"
        )

        if travel_known:
            block += (
                f"Travel fee: £{quote['travel_fee']:,.2f}\n"
                f"Estimated total: £{quote['quote_total']:,.2f}"
            )
        else:
            block += (
                "Estimated price before any travel adjustment: "
                f"£{quote['quote_total']:,.2f}"
            )

        blocks.append(block)

    answer_text = "\n\n".join(blocks)

    if len(comparison_quotes) == 2:
        difference = abs(
            comparison_quotes[0]["quote_total"]
            - comparison_quotes[1]["quote_total"]
        )
        answer_text += (
            "\n\n"
            f"Price difference: £{difference:,.2f}"
        )

    return {
        "answer_found": True,
        "answer_text": answer_text,
        "should_offer_human": False,
        "comparison_quotes": comparison_quotes,
        "comparison_mode": "PERSONALISED_TOTALS",
    }


# ------------------------------------------------------------------
# Expected State Handlers
# ------------------------------------------------------------------

def _wait_for_current_field(
    session: dict,
    field_name: str,
    language: str,
    *,
    unclear: bool = False,
) -> dict:
    return {
        "intent": "UPDATE_QUOTE",
        "language": language,
        "understanding": {
            "intent": "UPDATE_QUOTE",
            "needs_clarification": unclear,
        },
        "session": session,
        "action": "WAIT_FOR_FIELD_DECISION",
        "next_field": field_name,
        "options": get_available_options_for_field(
            field_name,
            session,
        ),
        "clarification": unclear,
    }


def _advance_after_field(
    session: dict,
    field_name: str,
    value: Any,
    language: str,
) -> dict:
    changed, accepted = _apply_one_field(
        session,
        field_name,
        value,
    )

    if not accepted:
        return _wait_for_current_field(
            session,
            field_name,
            language,
            unclear=True,
        )

    state = _set_quote_state_from_data(
        session,
        f"confirmed {field_name}",
    )

    if state == FlowState.QUOTE_READY.value:
        return {
            "intent": "UPDATE_QUOTE",
            "language": language,
            "understanding": {
                "intent": "UPDATE_QUOTE",
                "fields_to_update": [field_name],
                field_name: value,
            },
            "session": session,
            "action": "READY_FOR_QUOTE",
            "changed_fields": [field_name] if changed else [],
            "rejected_fields": [],
            "next_field": None,
            "options": [],
        }

    if state == FlowState.DEFERRED_REVIEW_READY.value:
        return {
            "intent": "UPDATE_QUOTE",
            "language": language,
            "understanding": {
                "intent": "UPDATE_QUOTE",
                "fields_to_update": [field_name],
                field_name: value,
            },
            "session": session,
            "action": "REVIEW_DEFERRED_FIELDS",
            "changed_fields": [field_name] if changed else [],
            "rejected_fields": [],
            "deferred_fields": get_deferred_quote_fields(
                session
            ),
        }

    next_field = expected_field_for_state(state)

    return {
        "intent": "UPDATE_QUOTE",
        "language": language,
        "understanding": {
            "intent": "UPDATE_QUOTE",
            "fields_to_update": [field_name],
            field_name: value,
        },
        "session": session,
        "action": "ASK_FOR_FIELD",
        "changed_fields": [field_name] if changed else [],
        "rejected_fields": [],
        "next_field": next_field,
        "options": (
            get_available_options_for_field(
                next_field,
                session,
            )
            if next_field
            else []
        ),
    }


def _defer_field(
    session: dict,
    field_name: str,
    language: str,
) -> dict:
    deferred = session.get(
        "deferred_quote_fields",
        [],
    )

    if not isinstance(deferred, list):
        deferred = []

    if field_name not in deferred:
        deferred.append(field_name)

    session["deferred_quote_fields"] = deferred
    session[field_name] = ""

    state = _set_quote_state_from_data(
        session,
        f"deferred uncertain {field_name}",
    )

    if state == FlowState.DEFERRED_REVIEW_READY.value:
        return {
            "intent": "UPDATE_QUOTE",
            "language": language,
            "understanding": {
                "intent": "UPDATE_QUOTE",
                "needs_clarification": True,
            },
            "session": session,
            "action": "REVIEW_DEFERRED_FIELDS",
            "changed_fields": [],
            "rejected_fields": [],
            "deferred_fields": get_deferred_quote_fields(
                session
            ),
        }

    next_field = expected_field_for_state(state)

    return {
        "intent": "UPDATE_QUOTE",
        "language": language,
        "understanding": {
            "intent": "UPDATE_QUOTE",
            "needs_clarification": True,
        },
        "session": session,
        "action": "ASK_FOR_FIELD",
        "changed_fields": [],
        "rejected_fields": [],
        "next_field": next_field,
        "options": (
            get_available_options_for_field(
                next_field,
                session,
            )
            if next_field
            else []
        ),
        "clarification": True,
        "deferred_field": field_name,
    }


def _handle_quote_field_state(
    session: dict,
    message_text: str,
    field_name: str,
) -> dict | None:
    options = get_available_options_for_field(
        field_name,
        session,
    )

    interpretation = interpret_expected_field_reply(
        field_name=field_name,
        message_text=message_text,
        allowed_options=options,
        current_conversation=session,
    )

    language = _language_of(interpretation)

    if interpretation.decision == "VALUE":
        value = _validate_quote_value(
            field_name,
            interpretation.normalized_value,
            session,
        )

        if value is None:
            return _wait_for_current_field(
                session,
                field_name,
                language,
                unclear=True,
            )

        return _advance_after_field(
            session,
            field_name,
            value,
            language,
        )

    if interpretation.decision == "PAUSE":
        return _wait_for_current_field(
            session,
            field_name,
            language,
        )

    if interpretation.decision == "UNCLEAR":
        return _defer_field(
            session,
            field_name,
            language,
        )

    # GENERAL_NLU: global semantic layer owns the message.
    return None


def _handle_package_reconfirmation(
    session: dict,
    message_text: str,
) -> dict | None:
    current_package = _clean_text(
        session.get(
            "package_reconfirmation_current"
        )
        or session.get("package")
    )

    options = get_packages_for_service(
        session.get("service")
    )

    interpretation = interpret_expected_field_reply(
        field_name="package_reconfirmation",
        message_text=message_text,
        allowed_options=options,
        current_conversation=session,
    )

    language = _language_of(interpretation)

    if interpretation.decision == "VALUE":
        selected_package = _canonical_from_list(
            interpretation.normalized_value,
            options,
        )

        if selected_package is None:
            return {
                "intent": "UPDATE_QUOTE",
                "language": language,
                "understanding": {
                    "intent": "UPDATE_QUOTE",
                },
                "session": session,
                "action": "WAIT_FOR_PACKAGE_RECONFIRMATION",
                "current_package": current_package,
                "options": options,
            }

        changed = (
            selected_package.lower()
            != current_package.lower()
        )

        session["package"] = selected_package
        session["package_reconfirmation_current"] = ""

        if changed:
            _invalidate_existing_quote(session)

        resume_state = pop_resume_state(
            session,
            default=FlowState.QUOTE_COVERAGE,
        )

        # If the old state is no longer valid, derive from current quote data.
        resume_field = expected_field_for_state(
            resume_state
        )

        if (
            resume_field
            and _has_value(session.get(resume_field))
        ):
            resume_state = _set_quote_state_from_data(
                session,
                "package reconfirmation resolved",
            )
        else:
            transition(
                session,
                resume_state,
                "package reconfirmation resolved",
            )

        session["package_reconfirmation_pending"] = False
        session["package_reconfirmation_resume_field"] = ""

        state = get_flow_state(session)

        if state == FlowState.QUOTE_READY.value:
            return {
                "intent": "UPDATE_QUOTE",
                "language": language,
                "understanding": {
                    "intent": "UPDATE_QUOTE",
                    "fields_to_update": ["package"],
                    "package": selected_package,
                },
                "session": session,
                "action": "READY_FOR_QUOTE",
                "changed_fields": ["package"] if changed else [],
                "rejected_fields": [],
                "next_field": None,
                "options": [],
            }

        next_field = expected_field_for_state(
            state
        )

        if next_field:
            return {
                "intent": "UPDATE_QUOTE",
                "language": language,
                "understanding": {
                    "intent": "UPDATE_QUOTE",
                    "fields_to_update": ["package"],
                    "package": selected_package,
                },
                "session": session,
                "action": "ASK_FOR_FIELD",
                "changed_fields": ["package"] if changed else [],
                "rejected_fields": [],
                "next_field": next_field,
                "options": get_available_options_for_field(
                    next_field,
                    session,
                ),
            }

        return {
            "intent": "UPDATE_QUOTE",
            "language": language,
            "understanding": {
                "intent": "UPDATE_QUOTE",
            },
            "session": session,
            "action": "CLARIFY",
        }

    if interpretation.decision in {
        "PAUSE",
        "UNCLEAR",
    }:
        return {
            "intent": "UPDATE_QUOTE",
            "language": language,
            "understanding": {
                "intent": "UPDATE_QUOTE",
            },
            "session": session,
            "action": "WAIT_FOR_PACKAGE_RECONFIRMATION",
            "current_package": current_package,
            "options": options,
        }

    return None


def _handle_deferred_review_state(
    session: dict,
    message_text: str,
) -> dict | None:
    interpretation = interpret_expected_field_reply(
        field_name="deferred_review_ready",
        message_text=message_text,
        allowed_options=[
            "Yes",
            "No",
        ],
        current_conversation=session,
    )

    language = _language_of(interpretation)

    if interpretation.decision == "VALUE":
        ready = _canonical_from_list(
            interpretation.normalized_value,
            [
                "Yes",
                "No",
            ],
        )

        if ready == "Yes":
            session["deferred_review_pending"] = False
            session["deferred_review_active"] = True
            session["status"] = "ACTIVE"
            session["current_stage"] = "AI_QUOTE"

            deferred = get_deferred_quote_fields(
                session
            )
            next_field = deferred[0] if deferred else None

            if not next_field:
                transition(
                    session,
                    FlowState.QUOTE_READY,
                    "deferred review had no unresolved fields",
                )
                return {
                    "intent": "UPDATE_QUOTE",
                    "language": language,
                    "understanding": {
                        "intent": "UPDATE_QUOTE",
                    },
                    "session": session,
                    "action": "READY_FOR_QUOTE",
                    "next_field": None,
                    "options": [],
                }

            transition(
                session,
                state_for_field(next_field),
                "customer started deferred review",
            )

            return {
                "intent": "UPDATE_QUOTE",
                "language": language,
                "understanding": {
                    "intent": "UPDATE_QUOTE",
                },
                "session": session,
                "action": "START_DEFERRED_REVIEW",
                "deferred_fields": deferred,
                "next_field": next_field,
                "options": get_available_options_for_field(
                    next_field,
                    session,
                ),
            }

        if ready == "No":
            session["deferred_review_pending"] = True
            session["deferred_review_active"] = False
            return {
                "intent": "UPDATE_QUOTE",
                "language": language,
                "understanding": {
                    "intent": "UPDATE_QUOTE",
                },
                "session": session,
                "action": "DEFERRED_REVIEW_PAUSED",
                "deferred_fields": get_deferred_quote_fields(
                    session
                ),
            }

    if interpretation.decision in {
        "PAUSE",
        "UNCLEAR",
    }:
        return {
            "intent": "UPDATE_QUOTE",
            "language": language,
            "understanding": {
                "intent": "UPDATE_QUOTE",
            },
            "session": session,
            "action": "DEFERRED_REVIEW_CONFIRMATION",
            "deferred_fields": get_deferred_quote_fields(
                session
            ),
        }

    return None


# ------------------------------------------------------------------
# Business-Question Interrupts
# ------------------------------------------------------------------

def _start_package_reconfirmation_if_needed(
    session: dict,
    question_type: str,
) -> None:
    if question_type not in {
        "PACKAGE_COMPARISON",
        "PACKAGE_COMPARISON_WITH_PRICING",
        "PACKAGE_RECOMMENDATION",
    }:
        return

    selected_package = _clean_text(
        session.get("package")
    )

    if not selected_package:
        return

    current_state = get_flow_state(session)

    if current_state == FlowState.PACKAGE_RECONFIRMATION.value:
        return

    push_resume_state(
        session,
        current_state,
    )

    session["package_reconfirmation_pending"] = True
    session["package_reconfirmation_current"] = selected_package
    session["package_reconfirmation_resume_field"] = (
        expected_field_for_state(current_state)
        or ""
    )

    transition(
        session,
        FlowState.PACKAGE_RECONFIRMATION,
        "package comparison interrupted selected package",
    )


def _business_answer(
    session: dict,
    understanding: CustomerMessageUnderstanding,
) -> dict:
    question_type = _clean_text(
        understanding.business_question_type
    ) or "GENERAL"

    question = _clean_text(
        understanding.business_question
    )

    requested_packages = list(
        understanding.requested_packages
        or []
    )

    _start_package_reconfirmation_if_needed(
        session,
        question_type,
    )

    if question_type == "CONTACT_PHONE_NUMBER":
        return {
            "intent": "BUSINESS_QUESTION",
            "language": understanding.language,
            "understanding": understanding.model_dump(),
            "session": session,
            "action": "SHOW_BUSINESS_PHONE",
            "business_question_type": question_type,
            "resume_prompt": _resume_prompt_for_state(
                session
            ),
        }

    comparison = None
    answer_found = False
    answer_text = ""
    should_offer_human = False

    if question_type == "PACKAGE_PRICING_COMPARISON":
        comparison = _build_package_price_comparison(
            session=session,
            requested_packages=requested_packages,
        )
        answer_found = comparison["answer_found"]
        answer_text = comparison["answer_text"]
        should_offer_human = comparison["should_offer_human"]

    elif question_type == "PACKAGE_COMPARISON_WITH_PRICING":
        grounded = answer_business_question(
            question=question,
            customer_language=understanding.language,
            current_conversation=session,
        )

        comparison = _build_package_price_comparison(
            session=session,
            requested_packages=requested_packages,
        )

        parts = []

        if grounded.answer_found and grounded.answer_text:
            parts.append(grounded.answer_text)

        if comparison["answer_found"] and comparison["answer_text"]:
            parts.append(
                "Pricing\n\n"
                + comparison["answer_text"]
            )

        answer_found = bool(parts)
        answer_text = "\n\n".join(parts)
        should_offer_human = (
            grounded.should_offer_human
            and comparison["should_offer_human"]
        )

    elif question_type == "PACKAGE_RECOMMENDATION":
        comparison = _build_package_price_comparison(
            session=session,
            requested_packages=(
                requested_packages
                or get_packages_for_service(
                    session.get("service")
                )
            ),
        )

        recommendation_context = dict(session)
        recommendation_context[
            "package_price_comparison"
        ] = comparison.get(
            "comparison_quotes",
            [],
        )
        recommendation_context[
            "package_price_comparison_travel_known"
        ] = _has_value(
            session.get("travel_required")
        )

        grounded = answer_business_question(
            question=question,
            customer_language=understanding.language,
            current_conversation=recommendation_context,
        )

        answer_found = grounded.answer_found
        answer_text = grounded.answer_text or ""
        should_offer_human = grounded.should_offer_human

    else:
        grounded = answer_business_question(
            question=question,
            customer_language=understanding.language,
            current_conversation=session,
        )
        answer_found = grounded.answer_found
        answer_text = grounded.answer_text or ""
        should_offer_human = grounded.should_offer_human

    session["last_business_question_type"] = question_type
    session["last_business_question_packages"] = requested_packages

    result = {
        "intent": "BUSINESS_QUESTION",
        "language": understanding.language,
        "understanding": understanding.model_dump(),
        "session": session,
        "action": "ANSWER_BUSINESS_QUESTION",
        "answer_found": answer_found,
        "answer_text": answer_text,
        "should_offer_human": should_offer_human,
        "business_question_type": question_type,
        "resume_prompt": _resume_prompt_for_state(
            session
        ),
    }

    if comparison:
        result.update(
            {
                "comparison_quotes": comparison.get(
                    "comparison_quotes",
                    [],
                ),
                "comparison_mode": comparison.get(
                    "comparison_mode"
                ),
            }
        )

    return result


# ------------------------------------------------------------------
# Full Semantic Layer
# ------------------------------------------------------------------

def _handle_full_understanding(
    session: dict,
    message_text: str,
) -> dict:
    understanding = understand_customer_message(
        message_text=message_text,
        current_conversation=session,
    )

    base = {
        "intent": understanding.intent,
        "language": understanding.language,
        "understanding": understanding.model_dump(),
        "session": session,
    }

    if understanding.intent == "SPEAK_TO_TEAM":
        return {
            **base,
            "action": "SPEAK_TO_TEAM",
        }

    if understanding.intent == "REQUEST_CALLBACK":
        return {
            **base,
            "action": "REQUEST_CALLBACK",
        }

    if understanding.intent == "BUSINESS_QUESTION":
        return _business_answer(
            session,
            understanding,
        )

    if understanding.intent in {
        "QUOTE_ENQUIRY",
        "UPDATE_QUOTE",
    }:
        session["selected_action"] = "GET_QUOTE"
        session["current_stage"] = "AI_QUOTE"

        applied = apply_customer_understanding(
            session,
            understanding,
        )

        # Unsupported service request: never invent or claim unavailable.
        if (
            understanding.requested_service_text
            and not understanding.service
            and "service" not in applied["changed_fields"]
        ):
            return {
                **base,
                "action": "SERVICE_NEEDS_HUMAN",
                "requested_service_text": (
                    understanding.requested_service_text
                ),
            }

        if (
            not applied["changed_fields"]
            and not applied["rejected_fields"]
            and understanding.needs_clarification
        ):
            return {
                **base,
                "action": "CLARIFY",
            }

        state = _set_quote_state_from_data(
            session,
            "applied full-message quote update",
        )

        if state == FlowState.QUOTE_READY.value:
            return {
                **base,
                "action": "READY_FOR_QUOTE",
                "changed_fields": applied["changed_fields"],
                "rejected_fields": applied["rejected_fields"],
                "next_field": None,
                "options": [],
            }

        if state == FlowState.DEFERRED_REVIEW_READY.value:
            return {
                **base,
                "action": "REVIEW_DEFERRED_FIELDS",
                "changed_fields": applied["changed_fields"],
                "rejected_fields": applied["rejected_fields"],
                "deferred_fields": get_deferred_quote_fields(
                    session
                ),
            }

        next_field = expected_field_for_state(state)

        if next_field:
            return {
                **base,
                "action": "ASK_FOR_FIELD",
                "changed_fields": applied["changed_fields"],
                "rejected_fields": applied["rejected_fields"],
                "next_field": next_field,
                "options": get_available_options_for_field(
                    next_field,
                    session,
                ),
            }

    state = get_flow_state(session)

    if understanding.intent == "GREETING":
        if state == FlowState.IDLE.value:
            return {
                **base,
                "action": "GREETING",
            }

        resume = _resume_prompt_for_state(session)
        return {
            **base,
            "action": "RESUME_CURRENT_STATE",
            "resume_prompt": resume,
        }

    # OTHER while a quote state is active should never throw the customer out
    # of the flow. Return to the current unresolved state.
    resume = _resume_prompt_for_state(session)

    if resume:
        return {
            **base,
            "action": "RESUME_CURRENT_STATE",
            "resume_prompt": resume,
        }

    return {
        **base,
        "action": "CLARIFY",
    }


# ------------------------------------------------------------------
# Public Orchestrator
# ------------------------------------------------------------------

def process_ai_customer_message(
    session: dict,
    message_text: str,
) -> dict:
    """Process one free-text customer message through Conversation Engine V2.

    Routing order is deliberately strict:

    1. Current state gets first chance to interpret the reply.
    2. A GENERAL_NLU outcome becomes a temporary global interrupt.
    3. Business questions are answered without destroying the underlying state.
    4. Python alone validates mutations and decides state transitions.
    """

    _ensure_state(session)
    state = get_flow_state(session)

    # --------------------------------------------------------------
    # State-specific interpretation
    # --------------------------------------------------------------
    if state == FlowState.PACKAGE_RECONFIRMATION.value:
        result = _handle_package_reconfirmation(
            session,
            message_text,
        )
        if result is not None:
            return result

    elif state == FlowState.DEFERRED_REVIEW_READY.value:
        result = _handle_deferred_review_state(
            session,
            message_text,
        )
        if result is not None:
            return result

    else:
        expected_field = expected_field_for_state(
            state
        )

        if expected_field:
            result = _handle_quote_field_state(
                session,
                message_text,
                expected_field,
            )
            if result is not None:
                return result

    # --------------------------------------------------------------
    # Global interrupt / multi-field understanding
    # --------------------------------------------------------------
    return _handle_full_understanding(
        session,
        message_text,
    )


# ------------------------------------------------------------------
# Session Lifecycle Helpers used by main.py
# ------------------------------------------------------------------

def initialize_new_quote_flow(
    session: dict,
) -> dict:
    session["selected_action"] = "GET_QUOTE"
    session["current_stage"] = "AI_QUOTE"
    session["deferred_quote_fields"] = []
    session["deferred_review_pending"] = False
    session["deferred_review_active"] = False
    session["package_reconfirmation_pending"] = False
    session["package_reconfirmation_current"] = ""
    session["package_reconfirmation_resume_field"] = ""
    session["resume_stack"] = []
    session["transition_log"] = []

    transition(
        session,
        FlowState.QUOTE_SERVICE,
        "new quote requested",
    )

    return session


def mark_flow_finished(
    session: dict,
) -> dict:
    clear_resume_stack(session)
    transition(
        session,
        FlowState.FINISHED,
        "conversation finished",
    )
    return session
