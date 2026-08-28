from ai_conversation_service import process_ai_customer_message

session = {
    "service": "Wedding",
    "package": "",
    "coverage_type": "Both",
    "travel_required": "",
    "duration_hours": 8,
    "event_date": "12 October",
    "location": "Birmingham",
    "quote_data": {},
    "status": "ACTIVE",
    "selected_action": "GET_QUOTE",
}

tests = [
    "Basic aur premium ka difference kya hai",
    "Which is good",
    "Okay give me pricing for both separately with spaces between",
    "I need both but a small space in between",
]

for index, message in enumerate(tests, start=1):
    print()
    print("=" * 72)
    print(f"TURN {index}")
    print("=" * 72)
    print("CUSTOMER:", message)

    result = process_ai_customer_message(
        session,
        message,
    )

    print("ACTION:", result.get("action"))
    print(
        "QUESTION TYPE:",
        result.get(
            "business_question_type",
            result.get(
                "understanding",
                {},
            ).get(
                "business_question_type"
            ),
        ),
    )
    print("ANSWER:", result.get("answer_text"))
    print("PACKAGE AFTER:", repr(session.get("package")))
    print(
        "LAST QUESTION TYPE:",
        session.get("last_business_question_type"),
    )
    print(
        "LAST PACKAGES:",
        session.get("last_business_question_packages"),
    )

    assert session.get("package", "") == "", (
        "A business question accidentally selected a package."
    )

print()
print("=" * 72)
print("CONVERSATION COMPARISON TEST COMPLETED")
print("=" * 72)
print(
    "Critical check: PACKAGE AFTER must remain '' for every turn."
)
print(
    "Pricing comparison should show Basic and Premium in separate blocks."
)
