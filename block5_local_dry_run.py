import main

from quote_service import (
    build_quote_message,
    calculate_quote,
)


# ------------------------------------------------------------------
# Local Output Adapter
# ------------------------------------------------------------------

def fake_send_instagram_menu(
    recipient_id: str,
    menu: dict,
):
    print()
    print("=" * 70)
    print("BOT MESSAGE")
    print("=" * 70)
    print(menu.get("message", ""))

    options = menu.get("options", [])

    if options:
        print()
        print("OPTIONS:")
        for option in options:
            print(
                f"- {option.get('title')} "
                f"[{option.get('payload')}]"
            )


# ------------------------------------------------------------------
# Local Quote Completion
# ------------------------------------------------------------------

def local_complete_quote(
    session: dict,
):
    """
    Use the real deterministic quote engine and real Pricing data,
    but do not write a Lead, send email, or call Instagram.
    """

    try:
        quote = calculate_quote(
            session=session,
        )

        quote_message = build_quote_message(
            session=session,
            quote=quote,
        )

        return {
            "success": True,
            "quote": quote,
            "lead": {
                "lead_id": "LOCAL-DRY-RUN",
            },
            "message": quote_message,
        }

    except Exception as error:
        return {
            "success": False,
            "message": (
                "Local quote calculation failed: "
                f"{error}"
            ),
        }


# ------------------------------------------------------------------
# Safe Local Overrides
# ------------------------------------------------------------------

main.send_instagram_menu = (
    fake_send_instagram_menu
)

main.complete_quote = (
    local_complete_quote
)


# ------------------------------------------------------------------
# Create Local Conversation
# ------------------------------------------------------------------

session = main.create_session(
    sender_id="LOCAL_CUSTOMER",
    recipient_id="LOCAL_BUSINESS",
    message_id="LOCAL_001",
)

session["selected_action"] = "GET_QUOTE"
session["current_stage"] = "AI_QUOTE"


# ------------------------------------------------------------------
# Conversation Turn 1
# ------------------------------------------------------------------

print()
print("# CUSTOMER TURN 1")
print(
    "Bhai wedding ke liye photo aur video chahiye "
    "Birmingham mein 12 October ko 8 hours"
)

main.handle_ai_customer_message(
    sender_id="LOCAL_CUSTOMER",
    session=session,
    message_text=(
        "Bhai wedding ke liye photo aur video chahiye "
        "Birmingham mein 12 October ko 8 hours"
    ),
)

print()
print("SESSION AFTER TURN 1:")
print(session)


# ------------------------------------------------------------------
# Conversation Turn 2
# ------------------------------------------------------------------

print()
print("# CUSTOMER TURN 2")
print("premium kar do")

main.handle_ai_customer_message(
    sender_id="LOCAL_CUSTOMER",
    session=session,
    message_text="premium kar do",
)

print()
print("SESSION AFTER TURN 2:")
print(session)


# ------------------------------------------------------------------
# Conversation Turn 3
# ------------------------------------------------------------------

print()
print("# CUSTOMER TURN 3")
print("travel nahi chahiye")

main.handle_ai_customer_message(
    sender_id="LOCAL_CUSTOMER",
    session=session,
    message_text="travel nahi chahiye",
)

print()
print("FINAL SESSION:")
print(session)

print()
print("=" * 70)
print("LOCAL DRY RUN COMPLETE")
print("=" * 70)
