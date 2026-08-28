import os
import re
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import HTMLResponse, PlainTextResponse
from pydantic import BaseModel, Field

from button_flow_service import get_menu_for_stage

from ai_conversation_service import (
    get_available_options_for_field,
    get_next_missing_quote_field,
    get_supported_services,
    initialize_new_quote_flow,
    mark_flow_finished,
    process_ai_customer_message,
)

from gemini_service import (
    generate_conversation_reply,
    interpret_expected_field_reply,
)

from instagram_service import send_instagram_menu

from email_service import (
    send_callback_request_email,
    send_customer_quote_email,
    send_handoff_notification,
    send_new_lead_email,
)

from quote_service import (
    build_quote_message,
    calculate_quote,
)

from sheets_service import (
    persist_completed_quote,
    save_completed_lead,
    update_lead,
)


# ------------------------------------------------------------------
# Project Configuration
# ------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent

load_dotenv(
    dotenv_path=BASE_DIR / ".env",
    override=True,
)


# ------------------------------------------------------------------
# FastAPI Application
# ------------------------------------------------------------------

app = FastAPI(
    title="Instagram Sales Automation API",
    description=(
        "Backend API for Instagram quote automation, "
        "FAQ routing, and human handoff."
    ),
    version="1.0.0",
)


# ------------------------------------------------------------------
# Environment Configuration
# ------------------------------------------------------------------

VERIFY_TOKEN = os.getenv(
    "META_VERIFY_TOKEN",
    "ai_quote_bot_verify_2026",
)

SUPPORT_EMAIL = os.getenv(
    "SUPPORT_EMAIL",
    "krishna.anepu@gmail.com",
)

INSTAGRAM_BUSINESS_ID = os.getenv(
    "INSTAGRAM_BUSINESS_ID"
)

BUSINESS_PHONE_NUMBER = os.getenv(
    "BUSINESS_PHONE_NUMBER",
    "",
).strip()


# ------------------------------------------------------------------
# Business Hours Configuration
# ------------------------------------------------------------------

UK_TIMEZONE = ZoneInfo(
    "Europe/London"
)

OFFICE_OPEN_HOUR = 9
OFFICE_CLOSE_HOUR = 17


def get_uk_now():
    return datetime.now(
        UK_TIMEZONE
    )


def is_office_open():
    uk_now = get_uk_now()

    return (
        OFFICE_OPEN_HOUR
        <= uk_now.hour
        < OFFICE_CLOSE_HOUR
    )


def utc_timestamp():
    return datetime.now(
        timezone.utc
    ).isoformat()


# ------------------------------------------------------------------
# In-Memory Conversation Sessions
# ------------------------------------------------------------------

conversation_sessions: dict[str, dict] = {}


def create_session(
    sender_id: str,
    recipient_id: str,
    message_id: str,
):
    session = {
        "sender_id": sender_id,
        "recipient_id": recipient_id,
        "current_stage": "WELCOME",
        "selected_action": "",
        "service": "",
        "package": "",
        "coverage_type": "",
        "travel_required": "",
        "duration_hours": "",
        "event_date": "",
        "location": "",
        "special_requirements": "",
        "customer_language": "English",
        "customer_email": "",
        "quote_email_sent": False,
        "customer_phone": "",
        "callback_preference": "",
        "handoff_requested": "",
        "handoff_requested_at": "",
        "handoff_status": "",
        "human_handoff": False,
        "handoff_message_sent": False,
        "handoff_acknowledged": False,
        "callback_request_sent": False,
        "active_lead_id": "",
        "quote_data": {},
        "lead_data": {},
        "expected_quote_field": "",
        "deferred_quote_fields": [],
        "deferred_review_pending": False,
        "deferred_review_active": False,
        "package_reconfirmation_pending": False,
        "package_reconfirmation_current": "",
        "package_reconfirmation_resume_field": "",
        "flow_state": "IDLE",
        "resume_stack": [],
        "transition_log": [],
        "status": "ACTIVE",
        "last_message_id": message_id,
    }

    conversation_sessions[sender_id] = session

    return session


def reset_session(
    sender_id: str,
    recipient_id: str,
    message_id: str,
):
    return create_session(
        sender_id=sender_id,
        recipient_id=recipient_id,
        message_id=message_id,
    )


def prepare_new_quote(
    session: dict,
):
    session.update(
        {
            "current_stage": "AI_QUOTE",
            "selected_action": "GET_QUOTE",
            "service": "",
            "package": "",
            "coverage_type": "",
            "travel_required": "",
            "duration_hours": "",
            "event_date": "",
            "location": "",
            "special_requirements": "",
            "customer_email": "",
            "quote_email_sent": False,
            "customer_phone": "",
            "callback_preference": "",
            "handoff_requested": "",
            "handoff_requested_at": "",
            "handoff_status": "",
            "human_handoff": False,
            "handoff_message_sent": False,
            "handoff_acknowledged": False,
            "callback_request_sent": False,
            "active_lead_id": "",
            "quote_data": {},
            "lead_data": {},
            "expected_quote_field": "",
            "deferred_quote_fields": [],
            "deferred_review_pending": False,
            "deferred_review_active": False,
            "package_reconfirmation_pending": False,
            "package_reconfirmation_current": "",
            "package_reconfirmation_resume_field": "",
            "flow_state": "QUOTE_SERVICE",
            "resume_stack": [],
            "transition_log": [],
            "status": "ACTIVE",
        }
    )

    initialize_new_quote_flow(session)
    return session


# ------------------------------------------------------------------
# Validation
# ------------------------------------------------------------------

def is_valid_email(
    email_address: str,
):
    pattern = (
        r"^[A-Za-z0-9._%+-]+"
        r"@[A-Za-z0-9.-]+"
        r"\.[A-Za-z]{2,}$"
    )

    return bool(
        re.match(
            pattern,
            email_address,
        )
    )


def is_valid_phone(
    phone_number: str,
):
    digits = re.sub(
        r"\D",
        "",
        phone_number,
    )

    return (
        7
        <= len(digits)
        <= 15
    )


# ------------------------------------------------------------------
# Button State Transitions
# ------------------------------------------------------------------

def process_session_button(
    session: dict,
    payload: str,
):
    if payload == "GET_QUOTE":
        prepare_new_quote(
            session
        )

    elif payload == "SPEAK_TO_TEAM":
        session["selected_action"] = "SPEAK_TO_TEAM"
        session["current_stage"] = "HUMAN_HANDOFF"
        session["status"] = "HUMAN_HANDOFF"
        session["human_handoff"] = True

    elif payload == "SERVICE_WEDDING":
        session["service"] = "Wedding"
        session["current_stage"] = "SELECT_PACKAGE"
        session["flow_state"] = "QUOTE_PACKAGE"
        session["expected_quote_field"] = "package"

    elif payload == "SERVICE_BIRTHDAY":
        session["service"] = "Birthday"
        session["current_stage"] = "SELECT_PACKAGE"
        session["flow_state"] = "QUOTE_PACKAGE"
        session["expected_quote_field"] = "package"

    elif payload == "SERVICE_PORTRAIT":
        session["service"] = "Portrait"
        session["current_stage"] = "SELECT_PACKAGE"
        session["flow_state"] = "QUOTE_PACKAGE"
        session["expected_quote_field"] = "package"

    elif payload == "SERVICE_EVENT":
        session["service"] = "Event"
        session["current_stage"] = "SELECT_PACKAGE"
        session["flow_state"] = "QUOTE_PACKAGE"
        session["expected_quote_field"] = "package"

    elif payload == "PACKAGE_BASIC":
        session["package"] = "Basic"
        session["current_stage"] = "SELECT_COVERAGE"
        session["flow_state"] = "QUOTE_COVERAGE"
        session["expected_quote_field"] = "coverage_type"

    elif payload == "PACKAGE_PREMIUM":
        session["package"] = "Premium"
        session["current_stage"] = "SELECT_COVERAGE"
        session["flow_state"] = "QUOTE_COVERAGE"
        session["expected_quote_field"] = "coverage_type"

    elif payload == "COVERAGE_PHOTOGRAPHY":
        session["coverage_type"] = "Photography"
        session["current_stage"] = "SELECT_TRAVEL"
        session["flow_state"] = "QUOTE_TRAVEL"
        session["expected_quote_field"] = "travel_required"

    elif payload == "COVERAGE_VIDEOGRAPHY":
        session["coverage_type"] = "Videography"
        session["current_stage"] = "SELECT_TRAVEL"
        session["flow_state"] = "QUOTE_TRAVEL"
        session["expected_quote_field"] = "travel_required"

    elif payload == "COVERAGE_BOTH":
        session["coverage_type"] = "Both"
        session["current_stage"] = "SELECT_TRAVEL"
        session["flow_state"] = "QUOTE_TRAVEL"
        session["expected_quote_field"] = "travel_required"

    elif payload == "TRAVEL_YES":
        session["travel_required"] = "Yes"
        session["current_stage"] = "SELECT_DURATION"
        session["flow_state"] = "QUOTE_DURATION"
        session["expected_quote_field"] = "duration_hours"

    elif payload == "TRAVEL_NO":
        session["travel_required"] = "No"
        session["current_stage"] = "SELECT_DURATION"
        session["flow_state"] = "QUOTE_DURATION"
        session["expected_quote_field"] = "duration_hours"

    elif payload == "EMAIL_YES":
        session["current_stage"] = "ENTER_CUSTOMER_EMAIL"
        session["status"] = "AWAITING_CUSTOMER_EMAIL"

    elif payload == "EMAIL_NO":
        session["current_stage"] = "POST_QUOTE_OPTIONS"
        session["status"] = "QUOTE_SENT"

    elif payload == "START_NEW_QUOTE":
        prepare_new_quote(
            session
        )

    elif payload == "REQUEST_CALLBACK":
        session["current_stage"] = "ENTER_CALLBACK_PHONE"
        session["status"] = "AWAITING_CALLBACK_PHONE"

    elif payload == "CALLBACK_ASAP":
        session["callback_preference"] = "ASAP"

    elif payload == "CALLBACK_MORNING":
        session["callback_preference"] = "Morning"

    elif payload == "CALLBACK_AFTERNOON":
        session["callback_preference"] = "Afternoon"

    elif payload == "FINISH":
        session["current_stage"] = "COMPLETED"
        session["status"] = "COMPLETED"
        mark_flow_finished(session)

    else:
        raise ValueError(
            f"Unknown button payload: {payload}"
        )

    return session


# ------------------------------------------------------------------
# Typed Quote Input State Transitions
# ------------------------------------------------------------------

def process_session_typed_input(
    session: dict,
    message_text: str,
):
    current_stage = session[
        "current_stage"
    ]

    if current_stage == "SELECT_DURATION":
        try:
            duration = float(
                message_text.strip()
            )
        except ValueError:
            return {
                "success": False,
                "message": (
                    "Please enter the number of hours, "
                    "for example 4, 6, or 8."
                ),
            }

        if duration <= 0:
            return {
                "success": False,
                "message": (
                    "Duration must be greater than zero."
                ),
            }

        if duration.is_integer():
            duration = int(duration)

        session["duration_hours"] = duration
        session["current_stage"] = "ENTER_EVENT_DATE"

        return {
            "success": True,
            "message": "Duration saved.",
            "session": session,
        }

    if current_stage == "ENTER_EVENT_DATE":
        event_date = message_text.strip()

        if not event_date:
            return {
                "success": False,
                "message": (
                    "Please enter the event date."
                ),
            }

        session["event_date"] = event_date
        session["current_stage"] = "ENTER_LOCATION"

        return {
            "success": True,
            "message": "Event date saved.",
            "session": session,
        }

    if current_stage == "ENTER_LOCATION":
        location = message_text.strip()

        if not location:
            return {
                "success": False,
                "message": (
                    "Please enter the event location."
                ),
            }

        session["location"] = location
        session["current_stage"] = "READY_FOR_QUOTE"
        session["status"] = "QUOTE_INPUT_COMPLETE"

        return {
            "success": True,
            "message": "Location saved.",
            "session": session,
        }

    return {
        "success": False,
        "message": (
            "Typed input is not expected "
            "at this stage."
        ),
    }


# ------------------------------------------------------------------
# Lead Helpers
# ------------------------------------------------------------------

def ensure_active_lead(
    session: dict,
):
    lead_data = session.get(
        "lead_data",
        {},
    )

    if lead_data.get(
        "lead_id"
    ):
        return lead_data

    existing_lead_id = session.get(
        "active_lead_id",
        "",
    )

    if existing_lead_id:
        return {
            "lead_id": existing_lead_id
        }

    session["status"] = "HUMAN_HANDOFF"
    session["human_handoff"] = True

    lead = save_completed_lead(
        session=session,
        quote_data={
            "status": "HUMAN_HANDOFF",
            "human_handoff": True,
        },
    )

    session["lead_data"] = lead

    return lead


def update_active_lead(
    session: dict,
    updates: dict,
):
    lead = ensure_active_lead(
        session
    )

    lead_id = lead.get(
        "lead_id"
    )

    if not lead_id:
        return None

    updated_lead = update_lead(
        lead_id=lead_id,
        updates=updates,
    )

    if updated_lead:
        session[
            "lead_data"
        ] = updated_lead

    return updated_lead


# ------------------------------------------------------------------
# Quote Calculation and Persistence
# ------------------------------------------------------------------

def complete_quote(
    session: dict,
):
    try:
        quote = calculate_quote(
            session=session,
        )

        session["status"] = "QUOTE_READY"

        existing_lead_id = session.get(
            "active_lead_id",
            "",
        )

        result = persist_completed_quote(
            session=session,
            quote_data=quote,
        )

        if existing_lead_id:
            updated_lead = update_lead(
                lead_id=existing_lead_id,
                updates={
                    "service": session.get("service", ""),
                    "package": session.get("package", ""),
                    "coverage_type": session.get("coverage_type", ""),
                    "event_date": session.get("event_date", ""),
                    "location": session.get("location", ""),
                    "duration_hours": session.get("duration_hours", ""),
                    "travel_required": session.get("travel_required", ""),
                    "base_price": quote.get("base_price", ""),
                    "extra_hours": quote.get("extra_hours", ""),
                    "extra_hour_rate": quote.get("extra_hour_rate", ""),
                    "travel_fee": quote.get("travel_fee", ""),
                    "quote_total": quote.get("quote_total", ""),
                    "status": quote.get("status", "QUOTE_READY"),
                    "human_handoff": quote.get("human_handoff", False),
                },
            )

            if updated_lead:
                result["lead"] = updated_lead

        quote_message = build_quote_message(
            session=session,
            quote=quote,
        )

        print(
            "Quote completed:",
            {
                "lead_id":
                    result["lead"]["lead_id"],
                "service":
                    session["service"],
                "package":
                    session["package"],
                "coverage":
                    session["coverage_type"],
                "quote_total":
                    quote["quote_total"],
            },
        )

        try:
            email_result = send_new_lead_email(
                session=session,
                quote=quote,
                lead=result["lead"],
            )

            print(
                "Business owner email sent:",
                email_result.get("id"),
            )

        except Exception as email_error:
            print(
                "Business owner email failed:",
                email_error,
            )

        return {
            "success": True,
            "quote": quote,
            "lead": result["lead"],
            "message": quote_message,
        }

    except Exception as error:
        print(
            "Quote calculation failed:",
            error,
        )

        return {
            "success": False,
            "message": (
                "Sorry, we could not calculate "
                "your quote right now. "
                "Please speak to our team "
                "for assistance."
            ),
        }


# ------------------------------------------------------------------
# Human Handoff
# ------------------------------------------------------------------

def _handoff_options():
    return [
        {
            "title": "Request Callback",
            "payload": "REQUEST_CALLBACK",
        },
        {
            "title": "Start New Quote",
            "payload": "START_NEW_QUOTE",
        },
        {
            "title": "Finish",
            "payload": "FINISH",
        },
    ]


def build_handoff_message(
    office_open: bool,
):
    if office_open:
        if BUSINESS_PHONE_NUMBER:
            message = (
                "I've shared your enquiry with our team. "
                "Our team is available from 9:00 AM to 5:00 PM UK time. "
                f"You can call us now on {BUSINESS_PHONE_NUMBER}. "
                "If the team is with another client or on a shoot, "
                "you can request a callback and we'll prioritise it."
            )
        else:
            message = (
                "I've shared your enquiry with our team. "
                "Our team is available from 9:00 AM to 5:00 PM UK time. "
                "If you'd prefer a call, use Request Callback below "
                "and we'll prioritise it."
            )
    else:
        message = (
            "I've shared your enquiry with our team. "
            "We're currently outside office hours, so it has been marked "
            "for priority follow-up during the next available office hours. "
            "You can also request a callback below."
        )

    return {
        "message": message,
        "options": _handoff_options(),
    }


def build_handoff_followup_message(
    session: dict,
):
    if (
        session.get("callback_request_sent")
        or session.get("handoff_status")
        == "CALLBACK_REQUESTED"
    ):
        return {
            "message": (
                "Your callback request is already recorded, so you don't "
                "need to confirm it again. Our team will follow up based on "
                "the preference you provided."
            ),
            "options": [
                {
                    "title": "Start New Quote",
                    "payload": "START_NEW_QUOTE",
                },
                {
                    "title": "Finish",
                    "payload": "FINISH",
                },
            ],
        }

    return {
        "message": (
            "Your enquiry is already with our team, so no extra confirmation "
            "is needed. If you'd like a callback, tap Request Callback below. "
            "You can also start a new quote or finish here."
        ),
        "options": _handoff_options(),
    }


def build_post_quote_options_menu():
    """
    Main choices shown after the quote/email step.

    The customer should never be left with only an open-ended
    "What would you like to do next?" message.
    """

    return {
        "message": (
            "What would you like to do next? "
            "You can speak to our team for more help, start a new quote, "
            "or finish here."
        ),
        "options": [
            {
                "title": "Speak to Team",
                "payload": "SPEAK_TO_TEAM",
            },
            {
                "title": "Start New Quote",
                "payload": "START_NEW_QUOTE",
            },
            {
                "title": "Finish",
                "payload": "FINISH",
            },
        ],
    }


def build_post_callback_options_menu():
    """
    Options shown after a callback has already been successfully recorded.

    Speak to Team is intentionally omitted here because the customer has
    just completed the human-contact/callback flow. If they later type a
    natural request to speak to the team, the AI intent layer can still
    handle that request.
    """

    return {
        "message": "What would you like to do next?",
        "options": [
            {
                "title": "Start New Quote",
                "payload": "START_NEW_QUOTE",
            },
            {
                "title": "Finish",
                "payload": "FINISH",
            },
        ],
    }


def build_callback_already_recorded_menu():
    return {
        "message": (
            "Your callback request is already recorded. "
            "There is no need to submit it again. Our team will follow up "
            "using the phone number and preference you provided."
        ),
        "options": [
            {
                "title": "Start New Quote",
                "payload": "START_NEW_QUOTE",
            },
            {
                "title": "Finish",
                "payload": "FINISH",
            },
        ],
    }


def is_short_handoff_acknowledgement(
    message_text: str,
) -> bool:
    normalized = (
        str(message_text or "")
        .strip()
        .lower()
    )

    normalized = re.sub(
        r"[^a-z0-9\s]",
        "",
        normalized,
    )

    normalized = " ".join(
        normalized.split()
    )

    return normalized in {
        "yes",
        "yes bro",
        "yes please",
        "yeah",
        "yep",
        "ok",
        "okay",
        "sure",
        "fine",
        "cool",
        "got it",
        "thanks",
        "thank you",
        "haan",
        "han",
        "ji",
    }


def process_handoff_request(
    session: dict,
):
    office_open = is_office_open()

    # The handoff may be requested again through natural-language replies.
    # Do not resend notifications or repeat the same first-time dialogue.
    if session.get("handoff_requested") == "Yes":
        session["current_stage"] = "POST_HANDOFF_OPTIONS"
        session["human_handoff"] = True

        return build_handoff_followup_message(
            session
        )

    session["handoff_requested"] = "Yes"
    session["handoff_requested_at"] = utc_timestamp()
    session["handoff_status"] = "REQUESTED"
    session["human_handoff"] = True
    session["handoff_message_sent"] = True
    session["status"] = "HUMAN_HANDOFF"
    session["current_stage"] = "POST_HANDOFF_OPTIONS"

    lead = ensure_active_lead(
        session
    )

    try:
        updated_lead = update_active_lead(
            session=session,
            updates={
                "human_handoff": True,
                "handoff_requested": "Yes",
                "handoff_requested_at":
                    session["handoff_requested_at"],
                "handoff_status": "REQUESTED",
                "status": "HUMAN_HANDOFF",
            },
        )

        if updated_lead:
            lead = updated_lead

    except Exception as error:
        print(
            "Handoff lead update failed:",
            error,
        )

    try:
        email_result = send_handoff_notification(
            session=session,
            lead=lead,
            office_open=office_open,
            business_phone=BUSINESS_PHONE_NUMBER,
        )

        print(
            "Handoff notification email sent:",
            email_result.get("id"),
        )

    except Exception as email_error:
        print(
            "Handoff notification email failed:",
            email_error,
        )

    customer_email = (
        session.get(
            "customer_email",
            "",
        )
        .strip()
        .lower()
    )

    quote_data = session.get(
        "quote_data",
        {},
    )

    quote_email_sent = bool(
        session.get(
            "quote_email_sent",
            False,
        )
    )

    # Business hours control live team availability, not quote email.
    # If we already know the customer's email and a final calculated
    # quote exists, make sure the actual quote has been emailed.
    if (
        customer_email
        and quote_data
        and not quote_email_sent
    ):
        try:
            customer_quote_result = (
                send_customer_quote_email(
                    customer_email=customer_email,
                    session=session,
                    quote=quote_data,
                    lead=lead,
                )
            )

            session[
                "quote_email_sent"
            ] = True

            print(
                "Customer final quote email sent during handoff:",
                customer_quote_result.get("id"),
            )

        except Exception as customer_email_error:
            print(
                "Customer final quote email during handoff failed:",
                customer_email_error,
            )

    session["current_stage"] = "POST_HANDOFF_OPTIONS"
    session["handoff_message_sent"] = True

    return build_handoff_message(
        office_open
    )


def start_callback_request(
    session: dict,
):
    """
    Start callback collection from either a button or a natural-language
    callback request.
    """

    if (
        session.get("callback_request_sent")
        or session.get("handoff_status")
        == "CALLBACK_REQUESTED"
    ):
        return {
            "already_recorded": True,
        }

    if not session.get(
        "handoff_requested_at"
    ):
        session[
            "handoff_requested_at"
        ] = utc_timestamp()

    session[
        "handoff_requested"
    ] = "Yes"

    session[
        "human_handoff"
    ] = True

    session[
        "current_stage"
    ] = "ENTER_CALLBACK_PHONE"

    session[
        "status"
    ] = "AWAITING_CALLBACK_PHONE"

    return {
        "already_recorded": False,
    }


def _deterministic_email_yes_no(
    message_text: str,
) -> str | None:
    normalized = (
        str(message_text or "")
        .strip()
        .lower()
    )

    normalized = re.sub(
        r"[^a-z0-9\s]",
        " ",
        normalized,
    )

    normalized = " ".join(
        normalized.split()
    )

    yes_values = {
        "yes",
        "yes please",
        "yeah",
        "yep",
        "sure",
        "send it",
        "send email",
        "email it",
        "haan",
        "han",
        "kavali",
    }

    no_values = {
        "no",
        "no thanks",
        "no thank you",
        "not now",
        "later",
        "nahi",
        "nahi chahiye",
        "vaddu",
    }

    if normalized in yes_values:
        return "Yes"

    if normalized in no_values:
        return "No"

    return None


def interpret_email_confirmation(
    session: dict,
    message_text: str,
) -> str:
    """
    Return YES, NO, UNCLEAR, or GENERAL_NLU for the post-quote email
    question. A side question must not make the email step disappear.
    """

    deterministic = (
        _deterministic_email_yes_no(
            message_text
        )
    )

    if deterministic:
        return deterministic.upper()

    try:
        interpretation = (
            interpret_expected_field_reply(
                field_name=
                    "email_quote_copy",
                message_text=
                    message_text,
                allowed_options=[
                    "Yes",
                    "No",
                ],
                current_conversation=
                    session,
            )
        )
    except Exception as error:
        print(
            "Email confirmation interpretation failed:",
            error,
        )

        return "GENERAL_NLU"

    if (
        interpretation.decision
        == "VALUE"
    ):
        value = str(
            interpretation.normalized_value
            or ""
        ).strip().lower()

        if value == "yes":
            return "YES"

        if value == "no":
            return "NO"

        return "UNCLEAR"

    if (
        interpretation.decision
        == "UNCLEAR"
    ):
        return "UNCLEAR"

    return "GENERAL_NLU"


def build_business_phone_message():
    """
    Return the configured business contact number without invoking Gemini.
    """

    if BUSINESS_PHONE_NUMBER:
        return (
            "Of course. You can reach our team on "
            f"{BUSINESS_PHONE_NUMBER}."
        )

    return (
        "I don't have a confirmed contact number configured at the moment. "
        "You can still use Speak to Team and our team will follow up."
    )


# ------------------------------------------------------------------
# AI Conversation Helpers
# ------------------------------------------------------------------

def build_ai_quote_start_menu():
    services = get_supported_services()

    if services:
        service_text = ", ".join(services)
        message = (
            "Tell us what you need for your event in your own words. "
            "You can include the service, package, photography or video, "
            "hours, date and location in one message. "
            f"Current services include: {service_text}."
        )
    else:
        message = (
            "Tell us what you need for your event in your own words. "
            "You can include the service, package, photography or video, "
            "hours, date and location in one message."
        )

    return {
        "message": message,
        "options": [],
    }


def build_fallback_ai_reply(
    action: str,
    next_field: str | None = None,
    options: list[str] | None = None,
    current_value: str | None = None,
):
    options = options or []

    if action == "GREETING":
        return "Hi! How can we help you today?"

    if action == "SERVICE_NEEDS_HUMAN":
        return (
            "I don't have confirmed information about that service "
            "at the moment. Would you like me to connect you with "
            "a team member?"
        )

    if action == "CLARIFY":
        return "Could you tell me a little more about what you need?"

    if action == "RECONFIRM_PACKAGE_SELECTION":
        other_options = [
            option
            for option in options
            if option.lower()
            != str(current_value or "").lower()
        ]

        switch_text = (
            other_options[0]
            if other_options
            else "another package"
        )

        return (
            f"You currently have {current_value} selected. "
            f"Would you like to continue with {current_value}, "
            f"or switch to {switch_text}?"
        )

    if action == "WAIT_FOR_PACKAGE_RECONFIRMATION":
        return (
            f"No problem. You currently have {current_value} selected. "
            "When you're ready, tell me whether you'd like to keep it "
            "or switch to another package."
        )

    if action == "WAIT_FOR_FIELD_DECISION":
        if next_field == "package":
            package_options = (
                ", ".join(options)
                if options
                else "the available package options"
            )
            return (
                "No problem, take your time. When you're ready to continue "
                f"the quote, choose the package that suits you best: "
                f"{package_options}."
            )

        return (
            "No problem, take your time. I still need that detail before "
            "I can continue with the final quote."
        )

    field_messages = {
        "service": "Which service do you need?",
        "package": "Which package would you like?",
        "coverage_type": "Do you need photography, videography, or both?",
        "travel_required": "Will travel be required for this booking?",
        "duration_hours": "How many hours of coverage do you need?",
        "event_date": "What is the event date?",
        "location": "Where will the event take place?",
    }

    message = field_messages.get(
        next_field,
        "What detail would you like to provide next?",
    )

    if options and next_field in {
        "service",
        "package",
    }:
        message += " Options: " + ", ".join(options) + "."

    return message


def safe_generate_ai_reply(
    action: str,
    customer_language: str,
    next_field: str | None = None,
    options: list[str] | None = None,
    requested_service_text: str | None = None,
    current_value: str | None = None,
):
    try:
        return generate_conversation_reply(
            action=action,
            customer_language=customer_language,
            next_field=next_field,
            options=options or [],
            requested_service_text=requested_service_text,
            current_value=current_value,
        )
    except Exception as error:
        print(
            "AI reply generation failed; using fallback:",
            error,
        )

        return build_fallback_ai_reply(
            action=action,
            next_field=next_field,
            options=options,
            current_value=current_value,
        )


def send_ai_missing_field_prompt(
    sender_id: str,
    session: dict,
    next_field: str,
):
    options = get_available_options_for_field(
        next_field,
        session,
    )

    message = safe_generate_ai_reply(
        action="ASK_FOR_FIELD",
        customer_language=session.get(
            "customer_language",
            "English",
        ),
        next_field=next_field,
        options=options,
    )

    send_instagram_menu(
        recipient_id=sender_id,
        menu={
            "message": message,
            "options": [],
        },
    )


def send_ai_resume_prompt(
    sender_id: str,
    session: dict,
    customer_language: str,
    resume_prompt: dict | None,
):
    """Return the customer to the authoritative state after an interrupt."""

    if not resume_prompt:
        return

    resume_action = resume_prompt.get("action")

    if resume_action == "ASK_FOR_FIELD":
        next_field = resume_prompt.get("next_field")
        if next_field:
            message = safe_generate_ai_reply(
                action="ASK_FOR_FIELD",
                customer_language=customer_language,
                next_field=next_field,
                options=resume_prompt.get("options", []),
            )
            send_instagram_menu(
                recipient_id=sender_id,
                menu={"message": message, "options": []},
            )
        return

    if resume_action == "RECONFIRM_PACKAGE_SELECTION":
        message = safe_generate_ai_reply(
            action="RECONFIRM_PACKAGE_SELECTION",
            customer_language=customer_language,
            next_field="package",
            options=resume_prompt.get("options", []),
            current_value=resume_prompt.get("current_value"),
        )
        send_instagram_menu(
            recipient_id=sender_id,
            menu={"message": message, "options": []},
        )
        return

    if resume_action == "REVIEW_DEFERRED_FIELDS":
        send_instagram_menu(
            recipient_id=sender_id,
            menu={
                "message": build_deferred_review_message(
                    resume_prompt.get("deferred_fields", [])
                ),
                "options": [],
            },
        )


DEFERRED_FIELD_LABELS = {
    "service": "service",
    "package": "package",
    "coverage_type": "coverage type",
    "travel_required": "travel requirement",
    "duration_hours": "coverage duration",
    "event_date": "event date",
    "location": "event location",
}


def build_deferred_review_message(
    deferred_fields: list[str],
) -> str:
    labels = [
        DEFERRED_FIELD_LABELS.get(
            field_name,
            field_name.replace("_", " "),
        )
        for field_name in deferred_fields
    ]

    if not labels:
        return (
            "We're almost done. I still need a few details confirmed "
            "before I can calculate your final quote. Are you ready to "
            "complete them now?"
        )

    if len(labels) == 1:
        detail_text = labels[0]

        return (
            "We're almost done. You weren't able to confirm your "
            f"{detail_text} earlier. I need that confirmed before I can "
            "calculate your final quote. Are you ready to complete it now?"
        )

    if len(labels) == 2:
        detail_text = (
            f"{labels[0]} and {labels[1]}"
        )
    else:
        detail_text = (
            ", ".join(labels[:-1])
            + f", and {labels[-1]}"
        )

    return (
        "We're almost done. There are a few details you weren't able "
        f"to confirm earlier: {detail_text}. I need these confirmed "
        "before I can calculate your final quote. Are you ready to "
        "complete them now?"
    )


def handle_ai_customer_message(
    sender_id: str,
    session: dict,
    message_text: str,
):
    try:
        result = process_ai_customer_message(
            session=session,
            message_text=message_text,
        )
    except Exception as error:
        print(
            "AI customer-message processing failed:",
            error,
        )

        send_instagram_menu(
            recipient_id=sender_id,
            menu={
                "message": (
                    "Sorry, we could not process that message right now. "
                    "You can try again or speak to our team."
                ),
                "options": [
                    {
                        "title": "Speak to Team",
                        "payload": "SPEAK_TO_TEAM",
                    }
                ],
            },
        )
        return

    customer_language = result.get(
        "language",
        "English",
    )
    session["customer_language"] = customer_language
    action = result["action"]

    if action in {
        "ASK_FOR_FIELD",
        "READY_FOR_QUOTE",
        "SERVICE_NEEDS_HUMAN",
        "START_DEFERRED_REVIEW",
        "WAIT_FOR_FIELD_DECISION",
        "WAIT_FOR_PACKAGE_RECONFIRMATION",
        "REVIEW_DEFERRED_FIELDS",
    }:
        session["selected_action"] = "GET_QUOTE"
        if session.get("current_stage") not in {
            "ASK_EMAIL_CONFIRMATION",
            "POST_QUOTE_OPTIONS",
        }:
            session["current_stage"] = "AI_QUOTE"

    if action == "SPEAK_TO_TEAM":
        handoff_menu = process_handoff_request(
            session=session,
        )
        send_instagram_menu(
            recipient_id=sender_id,
            menu=handoff_menu,
        )
        return

    if action == "REQUEST_CALLBACK":
        callback_result = start_callback_request(session)

        if callback_result.get("already_recorded"):
            send_instagram_menu(
                recipient_id=sender_id,
                menu=build_callback_already_recorded_menu(),
            )
        else:
            send_instagram_menu(
                recipient_id=sender_id,
                menu=get_menu_for_stage("ENTER_CALLBACK_PHONE"),
            )
        return

    if action == "SHOW_BUSINESS_PHONE":
        send_instagram_menu(
            recipient_id=sender_id,
            menu={
                "message": build_business_phone_message(),
                "options": [],
            },
        )
        send_ai_resume_prompt(
            sender_id=sender_id,
            session=session,
            customer_language=customer_language,
            resume_prompt=result.get("resume_prompt"),
        )
        return

    if action == "ANSWER_BUSINESS_QUESTION":
        answer_text = result.get("answer_text") or (
            "I don't have confirmed information about that at the moment."
        )
        options = []

        if result.get("should_offer_human"):
            options.append(
                {
                    "title": "Speak to Team",
                    "payload": "SPEAK_TO_TEAM",
                }
            )

        send_instagram_menu(
            recipient_id=sender_id,
            menu={
                "message": answer_text,
                "options": options,
            },
        )

        send_ai_resume_prompt(
            sender_id=sender_id,
            session=session,
            customer_language=customer_language,
            resume_prompt=result.get("resume_prompt"),
        )
        return

    if action == "RESUME_CURRENT_STATE":
        send_ai_resume_prompt(
            sender_id=sender_id,
            session=session,
            customer_language=customer_language,
            resume_prompt=result.get("resume_prompt"),
        )
        return

    if action == "GREETING":
        message = safe_generate_ai_reply(
            action="GREETING",
            customer_language=customer_language,
        )
        send_instagram_menu(
            recipient_id=sender_id,
            menu={
                "message": message,
                "options": [
                    {"title": "Get a Quote", "payload": "GET_QUOTE"},
                    {"title": "Speak to Team", "payload": "SPEAK_TO_TEAM"},
                ],
            },
        )
        return

    if action == "CLARIFY":
        message = safe_generate_ai_reply(
            action="CLARIFY",
            customer_language=customer_language,
        )
        send_instagram_menu(
            recipient_id=sender_id,
            menu={"message": message, "options": []},
        )
        return

    if action == "SERVICE_NEEDS_HUMAN":
        message = safe_generate_ai_reply(
            action="SERVICE_NEEDS_HUMAN",
            customer_language=customer_language,
            requested_service_text=result.get("requested_service_text"),
        )
        send_instagram_menu(
            recipient_id=sender_id,
            menu={
                "message": message,
                "options": [
                    {"title": "Speak to Team", "payload": "SPEAK_TO_TEAM"}
                ],
            },
        )
        return

    if action == "REVIEW_DEFERRED_FIELDS":
        deferred_fields = result.get("deferred_fields", [])
        session["current_stage"] = "AI_DEFERRED_CONFIRMATION"
        session["status"] = "AWAITING_DEFERRED_CONFIRMATION"
        send_instagram_menu(
            recipient_id=sender_id,
            menu={
                "message": build_deferred_review_message(deferred_fields),
                "options": [],
            },
        )
        return

    if action == "DEFERRED_REVIEW_CONFIRMATION":
        session["current_stage"] = "AI_DEFERRED_CONFIRMATION"
        send_instagram_menu(
            recipient_id=sender_id,
            menu={
                "message": (
                    "No problem. When you're ready to finish the remaining "
                    "details, just tell me and I'll continue with them."
                ),
                "options": [],
            },
        )
        return

    if action == "DEFERRED_REVIEW_PAUSED":
        session["current_stage"] = "AI_DEFERRED_CONFIRMATION"
        session["status"] = "AWAITING_DEFERRED_CONFIRMATION"
        send_instagram_menu(
            recipient_id=sender_id,
            menu={
                "message": (
                    "No problem. I'll keep the details you've already given. "
                    "I still need the remaining unconfirmed details before "
                    "I can calculate your final quote. When you're ready, "
                    "just tell me and we'll finish them."
                ),
                "options": [],
            },
        )
        return

    if action == "START_DEFERRED_REVIEW":
        next_field = result.get("next_field")
        if next_field:
            send_ai_missing_field_prompt(
                sender_id=sender_id,
                session=session,
                next_field=next_field,
            )
        return

    if action == "WAIT_FOR_PACKAGE_RECONFIRMATION":
        message = safe_generate_ai_reply(
            action="WAIT_FOR_PACKAGE_RECONFIRMATION",
            customer_language=customer_language,
            next_field="package",
            options=result.get("options", []),
            current_value=(
                result.get("current_package")
                or session.get("package")
            ),
        )
        send_instagram_menu(
            recipient_id=sender_id,
            menu={"message": message, "options": []},
        )
        return

    if action == "WAIT_FOR_FIELD_DECISION":
        next_field = result.get("next_field")
        message = safe_generate_ai_reply(
            action="WAIT_FOR_FIELD_DECISION",
            customer_language=customer_language,
            next_field=next_field,
            options=result.get("options", []),
        )
        send_instagram_menu(
            recipient_id=sender_id,
            menu={"message": message, "options": []},
        )
        return

    if action == "ASK_FOR_FIELD":
        next_field = result.get("next_field")
        if next_field:
            send_ai_missing_field_prompt(
                sender_id=sender_id,
                session=session,
                next_field=next_field,
            )
        return

    if action == "READY_FOR_QUOTE":
        quote_result = complete_quote(session=session)
        send_instagram_menu(
            recipient_id=sender_id,
            menu={
                "message": quote_result["message"],
                "options": [],
            },
        )

        if quote_result["success"]:
            session["quote_data"] = quote_result["quote"]
            session["lead_data"] = quote_result["lead"]
            session["quote_email_sent"] = False
            session["current_stage"] = "ASK_EMAIL_CONFIRMATION"
            session["status"] = "AWAITING_EMAIL_CONFIRMATION"
            send_instagram_menu(
                recipient_id=sender_id,
                menu=get_menu_for_stage("ASK_EMAIL_CONFIRMATION"),
            )
        return


# ------------------------------------------------------------------
# Instagram Webhook Models
# ------------------------------------------------------------------

class Sender(BaseModel):
    id: str


class Recipient(BaseModel):
    id: str


class QuickReply(BaseModel):
    payload: str | None = None


class Message(BaseModel):
    mid: str | None = None
    text: str | None = None
    quick_reply: QuickReply | None = None


class MessagingEvent(BaseModel):
    sender: Sender | None = None
    recipient: Recipient | None = None
    timestamp: int | None = None
    message: Message | None = None


class Entry(BaseModel):
    id: str
    time: int | None = None
    messaging: list[MessagingEvent] = Field(
        default_factory=list
    )


class InstagramWebhook(BaseModel):
    object: str
    entry: list[Entry] = Field(
        default_factory=list
    )


# ------------------------------------------------------------------
# Health Check
# ------------------------------------------------------------------

@app.get("/")
def health_check():
    return {
        "status": "running",
        "service": "Instagram Sales Automation API",
    }


# ------------------------------------------------------------------
# Privacy Policy
# ------------------------------------------------------------------

@app.get(
    "/privacy-policy",
    response_class=HTMLResponse,
)
def privacy_policy():
    return f"""
    <!DOCTYPE html>
    <html lang="en">

    <head>
        <meta charset="UTF-8">

        <meta
            name="viewport"
            content="width=device-width, initial-scale=1.0"
        >

        <title>
            Privacy Policy - Instagram Sales Automation
        </title>
    </head>

    <body style="
        max-width: 850px;
        margin: 40px auto;
        padding: 20px;
        font-family: Arial, sans-serif;
        line-height: 1.7;
        color: #222;
    ">

        <h1>Privacy Policy</h1>

        <p>
            <strong>Last updated:</strong>
            20 August 2026
        </p>

        <h2>1. Overview</h2>

        <p>
            This application helps businesses manage Instagram
            customer enquiries, collect quote requirements,
            provide customer support, and facilitate human
            follow-up when required.
        </p>

        <h2>2. Information We Process</h2>

        <ul>
            <li>Instagram-scoped user identifiers</li>
            <li>Instagram business account identifiers</li>
            <li>Message identifiers</li>
            <li>Message content</li>
            <li>Message timestamps</li>
            <li>
                Information voluntarily supplied during
                customer conversations
            </li>
        </ul>

        <h2>3. Purpose of Processing</h2>

        <p>
            Information may be processed to respond to customer
            enquiries, prepare quotations, maintain conversation
            context, support customer service, and facilitate
            human follow-up.
        </p>

        <h2>4. Data Sharing</h2>

        <p>
            Personal information processed by this application
            is not sold.
        </p>

        <h2>5. Data Retention</h2>

        <p>
            Information is retained only for as long as reasonably
            necessary for service delivery, business records,
            security, and applicable legal requirements.
        </p>

        <h2>6. Data Deletion</h2>

        <p>
            Data deletion instructions are available at:
            <a href="/data-deletion">
                Data Deletion Instructions
            </a>
        </p>

        <h2>7. Contact</h2>

        <p>
            Questions may be sent to:
            <a href="mailto:{SUPPORT_EMAIL}">
                {SUPPORT_EMAIL}
            </a>
        </p>

    </body>
    </html>
    """


# ------------------------------------------------------------------
# Terms of Service
# ------------------------------------------------------------------

@app.get(
    "/terms",
    response_class=HTMLResponse,
)
def terms_of_service():
    return f"""
    <!DOCTYPE html>
    <html lang="en">

    <head>
        <meta charset="UTF-8">

        <meta
            name="viewport"
            content="width=device-width, initial-scale=1.0"
        >

        <title>
            Terms of Service - Instagram Sales Automation
        </title>
    </head>

    <body style="
        max-width: 850px;
        margin: 40px auto;
        padding: 20px;
        font-family: Arial, sans-serif;
        line-height: 1.7;
        color: #222;
    ">

        <h1>Terms of Service</h1>

        <p>
            <strong>Last updated:</strong>
            20 August 2026
        </p>

        <h2>1. Service Description</h2>

        <p>
            This application provides automated functionality
            for handling Instagram customer enquiries,
            collecting quotation requirements, and assisting
            customer-service workflows.
        </p>

        <h2>2. Quotations</h2>

        <p>
            Quotations may be calculated using predefined
            business pricing and rules. Final pricing and
            availability may require business confirmation.
        </p>

        <h2>3. Automated Responses</h2>

        <p>
            Some customer interactions may be automated or
            assisted by artificial intelligence.
        </p>

        <h2>4. Third-Party Platforms</h2>

        <p>
            The application may rely on Meta, Instagram,
            Google, and other infrastructure providers.
        </p>

        <h2>5. Privacy</h2>

        <p>
            Information is processed according to the
            application's
            <a href="/privacy-policy">
                Privacy Policy
            </a>.
        </p>

        <h2>6. Contact</h2>

        <p>
            Questions may be sent to:
            <a href="mailto:{SUPPORT_EMAIL}">
                {SUPPORT_EMAIL}
            </a>
        </p>

    </body>
    </html>
    """


# ------------------------------------------------------------------
# Data Deletion
# ------------------------------------------------------------------

@app.get(
    "/data-deletion",
    response_class=HTMLResponse,
)
def data_deletion():
    return f"""
    <!DOCTYPE html>
    <html lang="en">

    <head>
        <meta charset="UTF-8">

        <meta
            name="viewport"
            content="width=device-width, initial-scale=1.0"
        >

        <title>
            Data Deletion - Instagram Sales Automation
        </title>
    </head>

    <body style="
        max-width: 850px;
        margin: 40px auto;
        padding: 20px;
        font-family: Arial, sans-serif;
        line-height: 1.7;
        color: #222;
    ">

        <h1>User Data Deletion Instructions</h1>

        <p>
            <strong>Last updated:</strong>
            20 August 2026
        </p>

        <p>
            Users may request deletion of personal information
            associated with their interactions with this
            application.
        </p>

        <p>
            Send deletion requests to:
        </p>

        <p>
            <a href="mailto:{SUPPORT_EMAIL}">
                {SUPPORT_EMAIL}
            </a>
        </p>

        <p>
            Please provide sufficient information to identify
            the relevant Instagram interaction.
        </p>

    </body>
    </html>
    """


# ------------------------------------------------------------------
# Meta Webhook Verification
# ------------------------------------------------------------------

@app.get(
    "/instagram/webhook",
    response_class=PlainTextResponse,
)
async def verify_instagram_webhook(
    request: Request,
):
    mode = request.query_params.get(
        "hub.mode"
    )

    token = request.query_params.get(
        "hub.verify_token"
    )

    challenge = request.query_params.get(
        "hub.challenge"
    )

    if (
        mode == "subscribe"
        and token == VERIFY_TOKEN
        and challenge is not None
    ):
        print(
            "Instagram webhook verification successful."
        )

        return challenge

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Webhook verification failed.",
    )


# ------------------------------------------------------------------
# Instagram Business Login Callback
# ------------------------------------------------------------------

@app.get("/instagram/callback")
async def instagram_login_callback(
    request: Request,
):
    authorization_code = (
        request.query_params.get("code")
    )

    error = request.query_params.get(
        "error"
    )

    if error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Instagram authorization "
                "was not completed."
            ),
        )

    if not authorization_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Authorization code "
                "was not provided."
            ),
        )

    return {
        "status": "authorization_received",
        "message": (
            "Instagram authorization code "
            "received successfully."
        ),
    }


# ------------------------------------------------------------------
# Instagram Messaging Webhook
# ------------------------------------------------------------------

@app.post("/instagram/webhook")
def receive_instagram_message(
    data: InstagramWebhook,
):
    for entry in data.entry:

        for event in entry.messaging:

            if (
                event.message is None
                or event.sender is None
                or event.recipient is None
            ):
                continue

            sender_id = event.sender.id
            recipient_id = event.recipient.id

            if (
                INSTAGRAM_BUSINESS_ID
                and str(sender_id)
                == str(INSTAGRAM_BUSINESS_ID)
            ):
                print(
                    "Ignoring outgoing business message:",
                    sender_id,
                )
                continue

            message_id = event.message.mid or ""
            message_text = event.message.text or ""
            timestamp = event.timestamp

            button_payload = None

            if event.message.quick_reply is not None:
                button_payload = (
                    event.message.quick_reply.payload
                )

            print(
                "Instagram message received:",
                {
                    "sender_id": sender_id,
                    "recipient_id": recipient_id,
                    "message_id": message_id,
                    "message": message_text,
                    "button_payload": button_payload,
                    "timestamp": timestamp,
                },
            )

            session = conversation_sessions.get(
                sender_id
            )

            if session is None:
                session = create_session(
                    sender_id=sender_id,
                    recipient_id=recipient_id,
                    message_id=message_id,
                )

                print(
                    "New in-memory conversation:",
                    sender_id,
                )

            session["last_message_id"] = message_id

            # ------------------------------------------------------
            # Button / Quick Reply Handling
            # ------------------------------------------------------

            if button_payload:
                try:
                    if button_payload == "REQUEST_CALLBACK":
                        callback_result = start_callback_request(
                            session
                        )

                        if callback_result.get(
                            "already_recorded"
                        ):
                            send_instagram_menu(
                                recipient_id=sender_id,
                                menu=build_callback_already_recorded_menu(),
                            )
                        else:
                            send_instagram_menu(
                                recipient_id=sender_id,
                                menu=get_menu_for_stage(
                                    "ENTER_CALLBACK_PHONE"
                                ),
                            )

                        continue

                    session = process_session_button(
                        session=session,
                        payload=button_payload,
                    )

                    if button_payload in {
                        "GET_QUOTE",
                        "START_NEW_QUOTE",
                    }:
                        session["current_stage"] = "AI_QUOTE"
                        session["selected_action"] = "GET_QUOTE"

                        send_instagram_menu(
                            recipient_id=sender_id,
                            menu=build_ai_quote_start_menu(),
                        )

                        continue

                    if button_payload == "SPEAK_TO_TEAM":
                        handoff_menu = process_handoff_request(
                            session=session,
                        )

                        send_instagram_menu(
                            recipient_id=sender_id,
                            menu=handoff_menu,
                        )

                        continue

                    if button_payload == "EMAIL_NO":
                        try:
                            update_active_lead(
                                session=session,
                                updates={
                                    "status":
                                        "QUOTE_SENT",
                                },
                            )
                        except Exception as error:
                            print(
                                "Lead status update failed:",
                                error,
                            )

                    if button_payload in {
                        "CALLBACK_ASAP",
                        "CALLBACK_MORNING",
                        "CALLBACK_AFTERNOON",
                    }:
                        if session.get(
                            "callback_request_sent"
                        ):
                            send_instagram_menu(
                                recipient_id=sender_id,
                                menu=build_callback_already_recorded_menu(),
                            )

                            continue

                        session["handoff_status"] = (
                            "CALLBACK_REQUESTED"
                        )
                        session["status"] = (
                            "CALLBACK_REQUESTED"
                        )

                        try:
                            updated_lead = update_active_lead(
                                session=session,
                                updates={
                                    "customer_phone":
                                        session[
                                            "customer_phone"
                                        ],
                                    "callback_preference":
                                        session[
                                            "callback_preference"
                                        ],
                                    "human_handoff": True,
                                    "handoff_requested": "Yes",
                                    "handoff_requested_at":
                                        session[
                                            "handoff_requested_at"
                                        ],
                                    "handoff_status":
                                        "CALLBACK_REQUESTED",
                                    "status":
                                        "CALLBACK_REQUESTED",
                                },
                            )

                            lead = (
                                updated_lead
                                or session.get(
                                    "lead_data",
                                    {},
                                )
                            )

                        except Exception as error:
                            print(
                                "Callback lead update failed:",
                                error,
                            )

                            lead = session.get(
                                "lead_data",
                                {},
                            )

                        try:
                            email_result = (
                                send_callback_request_email(
                                    session=session,
                                    lead=lead,
                                )
                            )

                            print(
                                "Callback request email sent:",
                                email_result.get("id"),
                            )

                        except Exception as email_error:
                            print(
                                "Callback request email failed:",
                                email_error,
                            )

                        session[
                            "callback_request_sent"
                        ] = True

                        if is_office_open():
                            callback_text = (
                                "Your callback request has been "
                                "sent to the team as a priority. "
                                "If the team is currently on a "
                                "shoot or with another client, "
                                "they will call you as soon as "
                                "they are available during "
                                "office hours."
                            )
                        else:
                            callback_text = (
                                "Your callback request has been "
                                "saved as a priority. The team "
                                "will contact you during the next "
                                "available office hours."
                            )

                        send_instagram_menu(
                            recipient_id=sender_id,
                            menu={
                                "message": callback_text,
                                "options": [],
                            },
                        )

                        session[
                            "current_stage"
                        ] = "CALLBACK_RECORDED"

                        send_instagram_menu(
                            recipient_id=sender_id,
                            menu=build_post_callback_options_menu(),
                        )

                        continue

                    send_instagram_menu(
                        recipient_id=sender_id,
                        menu=get_menu_for_stage(
                            session["current_stage"]
                        ),
                    )

                except Exception as error:
                    print(
                        "Button processing failed:",
                        error,
                    )

                continue

            current_stage = session[
                "current_stage"
            ]

            # ------------------------------------------------------
            # Quote Email Confirmation
            # ------------------------------------------------------
            #
            # A side question must not make the pending email decision vanish.
            # Answer the side question, then show the email Yes/No prompt again.

            if (
                current_stage
                == "ASK_EMAIL_CONFIRMATION"
                and message_text.strip()
            ):
                email_decision = (
                    interpret_email_confirmation(
                        session=session,
                        message_text=message_text,
                    )
                )

                if email_decision == "YES":
                    process_session_button(
                        session=session,
                        payload="EMAIL_YES",
                    )

                    send_instagram_menu(
                        recipient_id=sender_id,
                        menu=get_menu_for_stage(
                            "ENTER_CUSTOMER_EMAIL"
                        ),
                    )

                    continue

                if email_decision == "NO":
                    process_session_button(
                        session=session,
                        payload="EMAIL_NO",
                    )

                    send_instagram_menu(
                        recipient_id=sender_id,
                        menu=build_post_quote_options_menu(),
                    )

                    continue

                if email_decision == "UNCLEAR":
                    email_menu = get_menu_for_stage(
                        "ASK_EMAIL_CONFIRMATION"
                    )

                    send_instagram_menu(
                        recipient_id=sender_id,
                        menu={
                            "message": (
                                "No problem. Before we move on, would you "
                                "like a copy of your quote sent to your email?"
                            ),
                            "options":
                                email_menu.get(
                                    "options",
                                    [],
                                ),
                        },
                    )

                    continue

                handle_ai_customer_message(
                    sender_id=sender_id,
                    session=session,
                    message_text=message_text,
                )

                if (
                    session.get(
                        "current_stage"
                    )
                    == "ASK_EMAIL_CONFIRMATION"
                ):
                    send_instagram_menu(
                        recipient_id=sender_id,
                        menu=get_menu_for_stage(
                            "ASK_EMAIL_CONFIRMATION"
                        ),
                    )

                continue

            # ------------------------------------------------------
            # Customer Email Address Handling
            # ------------------------------------------------------

            if current_stage == "ENTER_CUSTOMER_EMAIL":
                customer_email = (
                    message_text
                    .strip()
                    .lower()
                )

                if not is_valid_email(
                    customer_email
                ):
                    send_instagram_menu(
                        recipient_id=sender_id,
                        menu={
                            "message": (
                                "That email address does not "
                                "look valid. Please enter it again."
                            ),
                            "options": [],
                        },
                    )
                    continue

                session["customer_email"] = customer_email

                quote_data = session.get(
                    "quote_data",
                    {},
                )

                lead_data = session.get(
                    "lead_data",
                    {},
                )

                if not quote_data or not lead_data:
                    send_instagram_menu(
                        recipient_id=sender_id,
                        menu={
                            "message": (
                                "We could not send the email "
                                "right now, but your quote is "
                                "still available here on Instagram."
                            ),
                            "options": [],
                        },
                    )

                    session[
                        "current_stage"
                    ] = "POST_QUOTE_OPTIONS"

                    send_instagram_menu(
                        recipient_id=sender_id,
                        menu=build_post_quote_options_menu(),
                    )

                    continue

                try:
                    email_result = send_customer_quote_email(
                        customer_email=customer_email,
                        session=session,
                        quote=quote_data,
                        lead=lead_data,
                    )

                    print(
                        "Customer quote email sent:",
                        email_result.get("id"),
                    )

                    update_active_lead(
                        session=session,
                        updates={
                            "customer_email":
                                customer_email,
                            "status":
                                "QUOTE_EMAILED",
                        },
                    )

                    session["status"] = "QUOTE_EMAILED"
                    session["quote_email_sent"] = True

                    send_instagram_menu(
                        recipient_id=sender_id,
                        menu={
                            "message": (
                                "Your quote has been sent "
                                "to your email."
                            ),
                            "options": [],
                        },
                    )

                except Exception as error:
                    print(
                        "Customer email failed:",
                        error,
                    )

                    try:
                        update_active_lead(
                            session=session,
                            updates={
                                "customer_email":
                                    customer_email,
                                "status":
                                    "EMAIL_SEND_FAILED",
                            },
                        )
                    except Exception as update_error:
                        print(
                            "Email failure lead update failed:",
                            update_error,
                        )

                    session["status"] = "EMAIL_SEND_FAILED"

                    send_instagram_menu(
                        recipient_id=sender_id,
                        menu={
                            "message": (
                                "We could not send the email "
                                "right now, but your quote is "
                                "still available here on Instagram."
                            ),
                            "options": [],
                        },
                    )

                session[
                    "current_stage"
                ] = "POST_QUOTE_OPTIONS"

                send_instagram_menu(
                    recipient_id=sender_id,
                    menu=build_post_quote_options_menu(),
                )

                continue

            # ------------------------------------------------------
            # Callback Phone Handling
            # ------------------------------------------------------

            if current_stage == "ENTER_CALLBACK_PHONE":
                customer_phone = (
                    message_text.strip()
                )

                if not is_valid_phone(
                    customer_phone
                ):
                    send_instagram_menu(
                        recipient_id=sender_id,
                        menu={
                            "message": (
                                "That phone number does not "
                                "look valid. Please enter a "
                                "valid phone number including "
                                "the area or country code."
                            ),
                            "options": [],
                        },
                    )
                    continue

                session[
                    "customer_phone"
                ] = customer_phone

                session[
                    "current_stage"
                ] = "SELECT_CALLBACK_PREFERENCE"

                session[
                    "status"
                ] = "AWAITING_CALLBACK_PREFERENCE"

                send_instagram_menu(
                    recipient_id=sender_id,
                    menu=get_menu_for_stage(
                        "SELECT_CALLBACK_PREFERENCE"
                    ),
                )

                continue

            # ------------------------------------------------------
            # Typed Quote Input Handling
            # ------------------------------------------------------

            if (
                session["selected_action"]
                == "GET_QUOTE"
                and current_stage
                in {
                    "SELECT_DURATION",
                    "ENTER_EVENT_DATE",
                    "ENTER_LOCATION",
                }
            ):
                try:
                    result = process_session_typed_input(
                        session=session,
                        message_text=message_text,
                    )

                    if not result["success"]:
                        send_instagram_menu(
                            recipient_id=sender_id,
                            menu={
                                "message":
                                    result["message"],
                                "options": [],
                            },
                        )
                        continue

                    current_stage = session[
                        "current_stage"
                    ]

                    if current_stage == "READY_FOR_QUOTE":
                        quote_result = complete_quote(
                            session=session,
                        )

                        send_instagram_menu(
                            recipient_id=sender_id,
                            menu={
                                "message":
                                    quote_result[
                                        "message"
                                    ],
                                "options": [],
                            },
                        )

                        if quote_result["success"]:
                            session[
                                "quote_data"
                            ] = quote_result["quote"]

                            session[
                                "lead_data"
                            ] = quote_result["lead"]

                            session[
                                "quote_email_sent"
                            ] = False

                            session[
                                "current_stage"
                            ] = "ASK_EMAIL_CONFIRMATION"

                            session[
                                "status"
                            ] = "AWAITING_EMAIL_CONFIRMATION"

                            send_instagram_menu(
                                recipient_id=sender_id,
                                menu=get_menu_for_stage(
                                    "ASK_EMAIL_CONFIRMATION"
                                ),
                            )

                        continue

                    send_instagram_menu(
                        recipient_id=sender_id,
                        menu=get_menu_for_stage(
                            current_stage
                        ),
                    )

                except Exception as error:
                    print(
                        "Typed input processing failed:",
                        error,
                    )

                continue

            # ------------------------------------------------------
            # Post-Quote Free-Text Questions
            # ------------------------------------------------------
            #
            # After answering another customer question, keep the three
            # next actions visible: Speak to Team, Start New Quote, Finish.

            if (
                current_stage
                == "POST_QUOTE_OPTIONS"
                and message_text.strip()
            ):
                handle_ai_customer_message(
                    sender_id=sender_id,
                    session=session,
                    message_text=message_text,
                )

                if (
                    session.get(
                        "current_stage"
                    )
                    == "POST_QUOTE_OPTIONS"
                ):
                    send_instagram_menu(
                        recipient_id=sender_id,
                        menu=build_post_quote_options_menu(),
                    )

                continue

            # ------------------------------------------------------
            # Human Handoff Stage
            # ------------------------------------------------------

            if current_stage in {
                "HUMAN_HANDOFF",
                "POST_HANDOFF_OPTIONS",
                "CALLBACK_RECORDED",
            }:
                if is_short_handoff_acknowledgement(
                    message_text
                ):
                    session[
                        "handoff_acknowledged"
                    ] = True

                    send_instagram_menu(
                        recipient_id=sender_id,
                        menu=build_handoff_followup_message(
                            session
                        ),
                    )

                    continue

                # Non-acknowledgement messages are allowed to fall through
                # to the normal AI layer so the customer can continue asking
                # business questions instead of being trapped in handoff state.

            # ------------------------------------------------------
            # Completed Conversation
            # ------------------------------------------------------

            if current_stage == "COMPLETED":
                reset_session(
                    sender_id=sender_id,
                    recipient_id=recipient_id,
                    message_id=message_id,
                )

                send_instagram_menu(
                    recipient_id=sender_id,
                    menu=get_menu_for_stage(
                        "WELCOME"
                    ),
                )

                continue

            # ------------------------------------------------------
            # AI Natural-Language Handling
            # ------------------------------------------------------

            if message_text.strip():
                handle_ai_customer_message(
                    sender_id=sender_id,
                    session=session,
                    message_text=message_text,
                )
                continue

            if current_stage == "WELCOME":
                send_instagram_menu(
                    recipient_id=sender_id,
                    menu=get_menu_for_stage(
                        "WELCOME"
                    ),
                )
                continue

            print(
                "Message received at stage:",
                current_stage,
            )

    return {
        "status": "received",
    }

