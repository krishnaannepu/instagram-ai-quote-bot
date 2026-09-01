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

messages = [
    "Basic aur premium ka difference kya hai",
    "Which is good",
    "Okay give me pricing for both separately with spaces between",
]

for number, message in enumerate(messages, start=1):
    print()
    print("=" * 72)
    print(f"TURN {number}")
    print("=" * 72)
    print("CUSTOMER:", message)

    result = process_ai_customer_message(
        session,
        message,
    )

    answer = result.get(
        "answer_text",
        "",
    )

    print(
        "QUESTION TYPE:",
        result.get(
            "business_question_type"
        ),
    )
    print("ANSWER:")
    print(answer)
    print(
        "PACKAGE AFTER:",
        repr(session.get("package")),
    )

    assert session.get("package", "") == ""
    assert "**" not in answer
    assert "__" not in answer
    assert "`" not in answer

    if (
        result.get("business_question_type")
        == "PACKAGE_RECOMMENDATION"
    ):
        assert "1,270" in answer
        assert "1,400" in answer
        assert "130" in answer or (
            "£1,270" in answer
            and "£1,400" in answer
        )

print()
print("=" * 72)
print("CONVERSATION POLISH TEST PASSED")
print("=" * 72)
print(
    "Recommendation must use the 8-hour totals, not only base prices."
)
print(
    "Customer-facing answers must contain no Markdown markers."
)
