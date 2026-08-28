import base64
import json
import os
from email.message import EmailMessage
from pathlib import Path

from dotenv import load_dotenv

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


# ------------------------------------------------------------------
# Project Configuration
# ------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent

ENV_FILE = BASE_DIR / ".env"

load_dotenv(
    dotenv_path=ENV_FILE,
    override=True,
)


# ------------------------------------------------------------------
# Gmail Configuration
# ------------------------------------------------------------------

GMAIL_CLIENT_FILE = (
    BASE_DIR
    / "credentials"
    / "gmail-oauth-client.json"
)

GMAIL_TOKEN_FILE = (
    BASE_DIR
    / "credentials"
    / "gmail-token.json"
)

GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.send"
]

# In Cloud Run, these values should come from Google Secret Manager
# as environment variables. Local development can continue using the
# JSON files in the credentials folder.
GMAIL_OAUTH_CLIENT_JSON = os.getenv(
    "GMAIL_OAUTH_CLIENT_JSON",
    "",
).strip()

GMAIL_TOKEN_JSON = os.getenv(
    "GMAIL_TOKEN_JSON",
    "",
).strip()

BUSINESS_OWNER_EMAIL = os.getenv(
    "BUSINESS_OWNER_EMAIL"
)


# ------------------------------------------------------------------
# Gmail Authentication
# ------------------------------------------------------------------

def get_gmail_service():
    credentials = None

    # --------------------------------------------------------------
    # Cloud Run / Secret Manager path
    # --------------------------------------------------------------

    if GMAIL_TOKEN_JSON:
        try:
            token_info = json.loads(
                GMAIL_TOKEN_JSON
            )

            credentials = (
                Credentials.from_authorized_user_info(
                    token_info,
                    GMAIL_SCOPES,
                )
            )

        except Exception as token_error:
            raise RuntimeError(
                "GMAIL_TOKEN_JSON could not be loaded."
            ) from token_error

    # --------------------------------------------------------------
    # Local development path
    # --------------------------------------------------------------

    elif GMAIL_TOKEN_FILE.exists():
        credentials = Credentials.from_authorized_user_file(
            str(GMAIL_TOKEN_FILE),
            GMAIL_SCOPES,
        )

    # --------------------------------------------------------------
    # Refresh an expired token
    # --------------------------------------------------------------

    if (
        credentials
        and not credentials.valid
        and credentials.expired
        and credentials.refresh_token
    ):
        credentials.refresh(
            Request()
        )

        # Local token files may be safely refreshed on disk.
        # Cloud Run secret values are intentionally not rewritten.
        if not GMAIL_TOKEN_JSON:
            GMAIL_TOKEN_FILE.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            GMAIL_TOKEN_FILE.write_text(
                credentials.to_json(),
                encoding="utf-8",
            )

    # --------------------------------------------------------------
    # First-time local OAuth only
    # --------------------------------------------------------------

    if credentials is None:
        if GMAIL_OAUTH_CLIENT_JSON:
            raise RuntimeError(
                "GMAIL_TOKEN_JSON is missing. "
                "Cloud Run cannot perform interactive Gmail OAuth. "
                "Create the Gmail token locally and store it in "
                "Secret Manager."
            )

        if not GMAIL_CLIENT_FILE.exists():
            raise FileNotFoundError(
                f"Gmail OAuth client file not found: "
                f"{GMAIL_CLIENT_FILE}"
            )

        flow = InstalledAppFlow.from_client_secrets_file(
            str(GMAIL_CLIENT_FILE),
            GMAIL_SCOPES,
        )

        credentials = flow.run_local_server(
            port=0
        )

        GMAIL_TOKEN_FILE.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        GMAIL_TOKEN_FILE.write_text(
            credentials.to_json(),
            encoding="utf-8",
        )

    if not credentials.valid:
        raise RuntimeError(
            "Gmail credentials are not valid."
        )

    return build(
        "gmail",
        "v1",
        credentials=credentials,
    )


# ------------------------------------------------------------------
# Generic Email Sending
# ------------------------------------------------------------------

def send_email(
    recipient: str,
    subject: str,
    body: str,
):
    if not recipient:
        raise ValueError(
            "Email recipient was not provided."
        )

    service = get_gmail_service()

    message = EmailMessage()

    message["To"] = recipient
    message["Subject"] = subject

    message.set_content(
        body
    )

    encoded_message = (
        base64.urlsafe_b64encode(
            message.as_bytes()
        )
        .decode()
    )

    result = (
        service
        .users()
        .messages()
        .send(
            userId="me",
            body={
                "raw": encoded_message
            },
        )
        .execute()
    )

    return result


# ------------------------------------------------------------------
# Business Owner Lead Notification
# ------------------------------------------------------------------

def send_new_lead_email(
    session: dict,
    quote: dict,
    lead: dict,
):
    if not BUSINESS_OWNER_EMAIL:
        raise ValueError(
            "BUSINESS_OWNER_EMAIL "
            "is missing from .env"
        )

    lead_id = lead.get(
        "lead_id",
        "",
    )

    subject = (
        "New Instagram Quote Lead - "
        f"{session['service']} - "
        f"{session['location']} - "
        f"£{quote['quote_total']:,.2f}"
    )

    body = (
        "A new Instagram quote enquiry "
        "has been completed.\n\n"

        f"Lead ID: {lead_id}\n"
        f"Service: {session['service']}\n"
        f"Package: {session['package']}\n"
        f"Coverage: {session['coverage_type']}\n"
        f"Event Date: {session['event_date']}\n"
        f"Location: {session['location']}\n"
        f"Duration: {session['duration_hours']} hours\n"
        f"Travel Required: "
        f"{session['travel_required']}\n\n"

        "Pricing\n"
        "------------------------------\n"

        f"Base Price: "
        f"£{quote['base_price']:,.2f}\n"

        f"Included Hours: "
        f"{quote['included_hours']:g}\n"

        f"Requested Hours: "
        f"{quote['duration_hours']:g}\n"

        f"Extra Hours: "
        f"{quote['extra_hours']:g}\n"

        f"Extra Hour Rate: "
        f"£{quote['extra_hour_rate']:,.2f}\n"

        f"Extra Hours Cost: "
        f"£{quote['extra_hours_cost']:,.2f}\n"

        f"Travel Fee: "
        f"£{quote['travel_fee']:,.2f}\n\n"

        "Calculations Involved\n"
        "------------------------------\n"

        f"Extra Hours = max("
        f"{quote['duration_hours']:g} - "
        f"{quote['included_hours']:g}, 0) "
        f"= {quote['extra_hours']:g}\n"

        f"Extra Hours Cost = "
        f"{quote['extra_hours']:g} × "
        f"£{quote['extra_hour_rate']:,.2f} "
        f"= £{quote['extra_hours_cost']:,.2f}\n"

        f"Final Quote = "
        f"£{quote['base_price']:,.2f} + "
        f"£{quote['extra_hours_cost']:,.2f} + "
        f"£{quote['travel_fee']:,.2f} "
        f"= £{quote['quote_total']:,.2f}\n\n"

        f"Estimated Quote: "
        f"£{quote['quote_total']:,.2f}\n\n"

        "The full enquiry has been saved "
        "to the Leads sheet.\n\n"

        "Please review availability and "
        "follow up with the customer "
        "through Instagram."
    )

    return send_email(
        recipient=BUSINESS_OWNER_EMAIL,
        subject=subject,
        body=body,
    )


# ------------------------------------------------------------------
# Customer Quote Email
# ------------------------------------------------------------------

def send_customer_quote_email(
    customer_email: str,
    session: dict,
    quote: dict,
    lead: dict,
):
    if not customer_email:
        raise ValueError(
            "Customer email was not provided."
        )

    lead_id = lead.get(
        "lead_id",
        "",
    )

    subject = (
        "Your Photography & Videography Quote - "
        f"{session['service']} - "
        f"£{quote['quote_total']:,.2f}"
    )

    body = (
        "Thank you for your enquiry "
        "with us.\n\n"

        "Your estimated quote details "
        "are below.\n\n"

        f"Reference: {lead_id}\n"
        f"Service: {session['service']}\n"
        f"Package: {session['package']}\n"
        f"Coverage: {session['coverage_type']}\n"
        f"Event Date: {session['event_date']}\n"
        f"Location: {session['location']}\n"
        f"Duration: {session['duration_hours']} hours\n"
        f"Travel Required: "
        f"{session['travel_required']}\n\n"

        "Pricing\n"
        "------------------------------\n"

        f"Base Price: "
        f"£{quote['base_price']:,.2f}\n"

        f"Included Hours: "
        f"{quote['included_hours']:g}\n"

        f"Requested Hours: "
        f"{quote['duration_hours']:g}\n"

        f"Extra Hours: "
        f"{quote['extra_hours']:g}\n"

        f"Extra Hour Rate: "
        f"£{quote['extra_hour_rate']:,.2f}\n"

        f"Extra Hours Cost: "
        f"£{quote['extra_hours_cost']:,.2f}\n"

        f"Travel Fee: "
        f"£{quote['travel_fee']:,.2f}\n\n"

        f"Estimated Total: "
        f"£{quote['quote_total']:,.2f}\n\n"

        "Please note that final pricing "
        "and availability may require "
        "business confirmation.\n\n"

        "Thank you,\n"
        "Our Team"
    )

    return send_email(
        recipient=customer_email,
        subject=subject,
        body=body,
    )


# ------------------------------------------------------------------
# Human Handoff Notification
# ------------------------------------------------------------------

def send_handoff_notification(
    session: dict,
    lead: dict,
    office_open: bool,
    business_phone: str = "",
):
    if not BUSINESS_OWNER_EMAIL:
        raise ValueError(
            "BUSINESS_OWNER_EMAIL "
            "is missing from .env"
        )

    lead_id = lead.get(
        "lead_id",
        "",
    )

    office_status = (
        "OPEN"
        if office_open
        else "CLOSED"
    )

    subject = (
        "Priority Instagram Handoff - "
        f"{lead_id or session.get('sender_id', '')}"
    )

    body = (
        "A customer has requested "
        "to speak to the team.\n\n"

        f"Lead ID: {lead_id}\n"

        f"Instagram Sender ID: "
        f"{session.get('sender_id', '')}\n"

        f"Service: "
        f"{session.get('service', '')}\n"

        f"Package: "
        f"{session.get('package', '')}\n"

        f"Event Date: "
        f"{session.get('event_date', '')}\n"

        f"Location: "
        f"{session.get('location', '')}\n"

        f"Quote Total: "
        f"{session.get('quote_data', {}).get('quote_total', '')}\n\n"

        f"Office Status: {office_status}\n"

        f"Business Phone: "
        f"{business_phone}\n\n"

        "Please review this enquiry "
        "as a priority."
    )

    return send_email(
        recipient=BUSINESS_OWNER_EMAIL,
        subject=subject,
        body=body,
    )


# ------------------------------------------------------------------
# Callback Request Notification
# ------------------------------------------------------------------

def send_callback_request_email(
    session: dict,
    lead: dict,
):
    if not BUSINESS_OWNER_EMAIL:
        raise ValueError(
            "BUSINESS_OWNER_EMAIL "
            "is missing from .env"
        )

    lead_id = lead.get(
        "lead_id",
        "",
    )

    subject = (
        "PRIORITY CALLBACK REQUEST - "
        f"{lead_id or session.get('sender_id', '')}"
    )

    body = (
        "A customer has requested "
        "a callback.\n\n"

        f"Lead ID: {lead_id}\n"

        f"Instagram Sender ID: "
        f"{session.get('sender_id', '')}\n"

        f"Customer Phone: "
        f"{session.get('customer_phone', '')}\n"

        f"Callback Preference: "
        f"{session.get('callback_preference', '')}\n\n"

        f"Service: "
        f"{session.get('service', '')}\n"

        f"Package: "
        f"{session.get('package', '')}\n"

        f"Coverage: "
        f"{session.get('coverage_type', '')}\n"

        f"Event Date: "
        f"{session.get('event_date', '')}\n"

        f"Location: "
        f"{session.get('location', '')}\n"

        f"Quote Total: "
        f"{session.get('quote_data', {}).get('quote_total', '')}\n\n"

        "Please contact this lead "
        "as a priority."
    )

    return send_email(
        recipient=BUSINESS_OWNER_EMAIL,
        subject=subject,
        body=body,
    )