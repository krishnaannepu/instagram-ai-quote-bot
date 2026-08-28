from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import (
    FastAPI,
    HTTPException,
    Request,
    status,
)
from fastapi.responses import (
    HTMLResponse,
    PlainTextResponse,
)

from v3_runtime_factory import (
    build_instagram_channel_v3,
)


# ------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------

BASE_DIR = Path(
    __file__
).resolve().parent

# While Block 11 is being validated inside v3_foundation, the existing
# production services live one level above. After the cutover files are copied
# to project root, BASE_DIR itself becomes PROJECT_ROOT.
PROJECT_ROOT = (
    BASE_DIR
    if (
        BASE_DIR
        / "business_knowledge_service.py"
    ).exists()
    else BASE_DIR.parent
)

load_dotenv(
    dotenv_path=
        PROJECT_ROOT
        / ".env",
    override=True,
)

VERIFY_TOKEN = os.getenv(
    "META_VERIFY_TOKEN",
    "ai_quote_bot_verify_2026",
)

SUPPORT_EMAIL = os.getenv(
    "SUPPORT_EMAIL",
    "",
).strip()


# ------------------------------------------------------------------
# FastAPI application
# ------------------------------------------------------------------

app = FastAPI(
    title="Instagram Sales Automation API",
    description=(
        "Backend API for Instagram quote automation, "
        "business enquiries, and human handoff."
    ),
    version="3.0.0",
)


# ------------------------------------------------------------------
# Lazy V3 runtime
# ------------------------------------------------------------------

_v3_channel = None


def get_v3_channel():
    """
    Build the V3 application graph only when the POST webhook is first used.

    Health/privacy/verification endpoints therefore stay available even if a
    downstream integration is temporarily unavailable during startup.
    """

    global _v3_channel

    if _v3_channel is None:
        _v3_channel = (
            build_instagram_channel_v3(
                project_root=
                    PROJECT_ROOT
            )
        )

    return _v3_channel


# ------------------------------------------------------------------
# Health
# ------------------------------------------------------------------

@app.get("/")
def health_check():
    return {
        "status":
            "running",
        "service":
            "Instagram Sales Automation API",
        "conversation_engine":
            "v3",
    }


# ------------------------------------------------------------------
# Privacy Policy
# ------------------------------------------------------------------

@app.get(
    "/privacy-policy",
    response_class=
        HTMLResponse,
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
        <title>Privacy Policy - Instagram Sales Automation</title>
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
        <p><strong>Last updated:</strong> 20 August 2026</p>

        <h2>1. Overview</h2>
        <p>
            This application helps businesses manage Instagram customer
            enquiries, collect quote requirements, provide customer support,
            and facilitate human follow-up when required.
        </p>

        <h2>2. Information We Process</h2>
        <ul>
            <li>Instagram-scoped user identifiers</li>
            <li>Instagram business account identifiers</li>
            <li>Message identifiers</li>
            <li>Message content</li>
            <li>Message timestamps</li>
            <li>Information voluntarily supplied during customer conversations</li>
        </ul>

        <h2>3. Purpose of Processing</h2>
        <p>
            Information may be processed to respond to customer enquiries,
            prepare quotations, maintain conversation context, support
            customer service, and facilitate human follow-up.
        </p>

        <h2>4. Data Sharing</h2>
        <p>Personal information processed by this application is not sold.</p>

        <h2>5. Data Retention</h2>
        <p>
            Information is retained only for as long as reasonably necessary
            for service delivery, business records, security, and applicable
            legal requirements.
        </p>

        <h2>6. Data Deletion</h2>
        <p>
            Data deletion instructions are available at
            <a href="/data-deletion">Data Deletion Instructions</a>.
        </p>

        <h2>7. Contact</h2>
        <p>
            Questions may be sent to
            <a href="mailto:{SUPPORT_EMAIL}">{SUPPORT_EMAIL}</a>.
        </p>
    </body>
    </html>
    """


# ------------------------------------------------------------------
# Terms
# ------------------------------------------------------------------

@app.get(
    "/terms",
    response_class=
        HTMLResponse,
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
        <title>Terms of Service - Instagram Sales Automation</title>
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
        <p><strong>Last updated:</strong> 20 August 2026</p>

        <h2>1. Service Description</h2>
        <p>
            This application provides automated functionality for handling
            Instagram customer enquiries, collecting quotation requirements,
            and assisting customer-service workflows.
        </p>

        <h2>2. Quotations</h2>
        <p>
            Quotations may be calculated using predefined business pricing
            and rules. Final pricing and availability may require business
            confirmation.
        </p>

        <h2>3. Automated Responses</h2>
        <p>
            Some customer interactions may be automated or assisted by
            artificial intelligence.
        </p>

        <h2>4. Third-Party Platforms</h2>
        <p>
            The application may rely on Meta, Instagram, Google, and other
            infrastructure providers.
        </p>

        <h2>5. Privacy</h2>
        <p>
            Information is processed according to the application's
            <a href="/privacy-policy">Privacy Policy</a>.
        </p>

        <h2>6. Contact</h2>
        <p>
            Questions may be sent to
            <a href="mailto:{SUPPORT_EMAIL}">{SUPPORT_EMAIL}</a>.
        </p>
    </body>
    </html>
    """


# ------------------------------------------------------------------
# Data deletion
# ------------------------------------------------------------------

@app.get(
    "/data-deletion",
    response_class=
        HTMLResponse,
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
        <title>Data Deletion - Instagram Sales Automation</title>
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
        <p><strong>Last updated:</strong> 20 August 2026</p>

        <p>
            Users may request deletion of personal information associated with
            their interactions with this application.
        </p>

        <p>Send deletion requests to:</p>

        <p>
            <a href="mailto:{SUPPORT_EMAIL}">{SUPPORT_EMAIL}</a>
        </p>

        <p>
            Please provide sufficient information to identify the relevant
            Instagram interaction.
        </p>
    </body>
    </html>
    """


# ------------------------------------------------------------------
# Meta webhook verification
# ------------------------------------------------------------------

@app.get(
    "/instagram/webhook",
    response_class=
        PlainTextResponse,
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
        status_code=
            status.HTTP_403_FORBIDDEN,
        detail=
            "Webhook verification failed.",
    )


# ------------------------------------------------------------------
# Instagram Business Login callback
# ------------------------------------------------------------------

@app.get(
    "/instagram/callback"
)
async def instagram_login_callback(
    request: Request,
):
    authorization_code = (
        request.query_params.get(
            "code"
        )
    )

    error = request.query_params.get(
        "error"
    )

    if error:
        raise HTTPException(
            status_code=
                status.HTTP_400_BAD_REQUEST,
            detail=(
                "Instagram authorization "
                "was not completed."
            ),
        )

    if not authorization_code:
        raise HTTPException(
            status_code=
                status.HTTP_400_BAD_REQUEST,
            detail=(
                "Authorization code "
                "was not provided."
            ),
        )

    return {
        "status":
            "authorization_received",
        "message": (
            "Instagram authorization code "
            "received successfully."
        ),
    }


# ------------------------------------------------------------------
# Instagram Messaging Webhook — V3 hard cutover
# ------------------------------------------------------------------

@app.post(
    "/instagram/webhook"
)
def receive_instagram_message(
    payload: dict,
):
    """
    Final controller shape:

        Meta payload
        -> V3 channel adapter
        -> V3 runtime
        -> one authoritative state machine

    There is intentionally no quote/business/email/handoff routing here.
    """

    try:
        result = (
            get_v3_channel()
            .process_webhook(
                payload
            )
        )

    except Exception as error:
        print(
            "V3 webhook processing failed:",
            repr(
                error
            ),
        )

        raise HTTPException(
            status_code=
                status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=
                "Webhook processing failed.",
        ) from error

    return {
        "status":
            "received",
        "processed_messages":
            result.processed_messages,
        "ignored_messages":
            result.ignored_messages,
        "conversation_engine":
            "v3",
    }
