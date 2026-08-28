import os

import httpx
from dotenv import load_dotenv


# ------------------------------------------------------------------
# Environment Configuration
# ------------------------------------------------------------------

load_dotenv()

INSTAGRAM_ACCESS_TOKEN = os.getenv(
    "INSTAGRAM_ACCESS_TOKEN"
)

INSTAGRAM_BUSINESS_ID = os.getenv(
    "INSTAGRAM_BUSINESS_ID"
)

META_API_VERSION = os.getenv(
    "META_API_VERSION"
)


if not INSTAGRAM_ACCESS_TOKEN:
    raise ValueError(
        "INSTAGRAM_ACCESS_TOKEN is not configured."
    )

if not INSTAGRAM_BUSINESS_ID:
    raise ValueError(
        "INSTAGRAM_BUSINESS_ID is not configured."
    )

if not META_API_VERSION:
    raise ValueError(
        "META_API_VERSION is not configured."
    )


# ------------------------------------------------------------------
# Instagram Send API
# ------------------------------------------------------------------

def send_instagram_menu(
    recipient_id: str,
    menu: dict,
):
    url = (
        f"https://graph.instagram.com/"
        f"{META_API_VERSION}/"
        f"{INSTAGRAM_BUSINESS_ID}/messages"
    )

    quick_replies = []

    for option in menu.get("options", []):
        quick_replies.append(
            {
                "content_type": "text",
                "title": option["title"],
                "payload": option["payload"],
            }
        )

    message = {
        "text": menu["message"],
    }

    if quick_replies:
        message["quick_replies"] = quick_replies

    payload = {
        "recipient": {
            "id": recipient_id,
        },
        "messaging_type": "RESPONSE",
        "message": message,
    }

    headers = {
        "Authorization": (
            f"Bearer {INSTAGRAM_ACCESS_TOKEN}"
        ),
        "Content-Type": "application/json",
    }

    response = httpx.post(
        url,
        json=payload,
        headers=headers,
        timeout=15.0,
    )

    response.raise_for_status()

    return response.json()