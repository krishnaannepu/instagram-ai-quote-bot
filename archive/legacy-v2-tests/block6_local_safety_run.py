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
    print("=" * 72)
    print("BOT MESSAGE")
    print("=" * 72)
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
            "lead_id": "LOCAL-SAFETY-RUN",
        },
        "message": quote_message,
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
# Session
# ------------------------------------------------------------------

session = main.create_session(
    sender_id="LOCAL_CUSTOMER",
    recipient_id="LOCAL_BUSINESS",
    message_id="LOCAL_SAFETY_001",
)

session["selected_action"] = "GET_QUOTE"
session["current_stage"] = "AI_QUOTE"


def show_session(label: str):
    print()
    print(label)
    print(
        {
            "service": session.get("service"),
            "package": session.get("package"),
            "coverage_type": session.get("coverage_type"),
            "travel_required": session.get("travel_required"),
            "duration_hours": session.get("duration_hours"),
            "event_date": session.get("event_date"),
            "location": session.get("location"),
            "current_stage": session.get("current_stage"),
            "status": session.get("status"),
            "quote_total": (
                session.get("quote_data", {})
                .get("quote_total")
            ),
        }
    )


# ------------------------------------------------------------------
# Turn 1 - Multi-field enquiry
# ------------------------------------------------------------------

print("\n# TURN 1 - CUSTOMER")
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

show_session("SESSION AFTER TURN 1")


# ------------------------------------------------------------------
# Turn 2 - Business question, not a package selection
# ------------------------------------------------------------------

print("\n# TURN 2 - CUSTOMER")
print("premium kya hota hai?")

main.handle_ai_customer_message(
    sender_id="LOCAL_CUSTOMER",
    session=session,
    message_text="premium kya hota hai?",
)

show_session("SESSION AFTER TURN 2")


# ------------------------------------------------------------------
# Turn 3 - Actual package selection
# ------------------------------------------------------------------

print("\n# TURN 3 - CUSTOMER")
print("premium kar do")

main.handle_ai_customer_message(
    sender_id="LOCAL_CUSTOMER",
    session=session,
    message_text="premium kar do",
)

show_session("SESSION AFTER TURN 3")


# ------------------------------------------------------------------
# Turn 4 - Travel answer completes quote
# ------------------------------------------------------------------

print("\n# TURN 4 - CUSTOMER")
print("travel nahi chahiye")

main.handle_ai_customer_message(
    sender_id="LOCAL_CUSTOMER",
    session=session,
    message_text="travel nahi chahiye",
)

show_session("SESSION AFTER TURN 4")


# ------------------------------------------------------------------
# Turn 5 - Change an already generated quote
# ------------------------------------------------------------------

print("\n# TURN 5 - CUSTOMER")
print("actually basic kar do")

main.handle_ai_customer_message(
    sender_id="LOCAL_CUSTOMER",
    session=session,
    message_text="actually basic kar do",
)

show_session("SESSION AFTER TURN 5")


# ------------------------------------------------------------------
# Assertions
# ------------------------------------------------------------------

assert session["service"] == "Wedding"
assert session["package"] == "Basic"
assert session["coverage_type"] == "Both"
assert session["travel_required"] == "No"
assert session["duration_hours"] == 8
assert session["event_date"] == "12 October"
assert session["location"] == "Birmingham"

# Wedding Basic Both = £950 base, 4 included hours,
# 4 extra hours × £80 = £320, total £1,270.
assert session["quote_data"]["quote_total"] == 1270.0

print()
print("=" * 72)
print("BLOCK 6 LOCAL SAFETY RUN PASSED")
print("=" * 72)
