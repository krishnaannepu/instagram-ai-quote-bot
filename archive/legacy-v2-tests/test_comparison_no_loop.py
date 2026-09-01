from ai_conversation_service import (
    _build_package_price_comparison,
    process_ai_customer_message,
)

# --------------------------------------------------------------
# Direct Python test: comparison must not ask coverage/duration.
# --------------------------------------------------------------

session = {
    "service": "Wedding",
    "package": "",
    "coverage_type": "",
    "travel_required": "",
    "duration_hours": "",
    "event_date": "",
    "location": "",
    "quote_data": {},
    "status": "ACTIVE",
    "selected_action": "GET_QUOTE",
    "last_business_question_type":
        "PACKAGE_COMPARISON",
    "last_business_question_packages":
        ["Basic", "Premium"],
}

comparison = _build_package_price_comparison(
    session=session,
    requested_packages=[
        "Basic",
        "Premium",
    ],
)

print("=" * 72)
print("DIRECT PRICING COMPARISON")
print("=" * 72)
print("MODE:", comparison.get("comparison_mode"))
print("MISSING:", comparison.get("comparison_missing_field"))
print("ANSWER:")
print(comparison.get("answer_text"))
print("PACKAGE AFTER:", repr(session.get("package")))

assert comparison.get("comparison_missing_field") is None
assert comparison.get("comparison_mode") == "CATALOGUE_PRICING"
assert "Photography:" in comparison["answer_text"]
assert "Videography:" in comparison["answer_text"]
assert "Both:" in comparison["answer_text"]
assert "Basic" in comparison["answer_text"]
assert "Premium" in comparison["answer_text"]
assert session.get("package", "") == ""

# --------------------------------------------------------------
# Real NLU conversation checks matching the Instagram problem.
# --------------------------------------------------------------

messages = [
    "Paisa??",
    "Compare separately",
    "Compare with both and separately as well",
]

for number, message in enumerate(
    messages,
    start=1,
):
    print()
    print("=" * 72)
    print(f"TURN {number}")
    print("=" * 72)
    print("CUSTOMER:", message)

    result = process_ai_customer_message(
        session,
        message,
    )

    print(
        "ACTION:",
        result.get("action"),
    )
    print(
        "QUESTION TYPE:",
        result.get(
            "business_question_type"
        ),
    )
    print(
        "COMPARISON MODE:",
        result.get(
            "comparison_mode"
        ),
    )
    print("ANSWER:")
    print(
        result.get(
            "answer_text",
            "",
        )
    )
    print(
        "PACKAGE AFTER:",
        repr(
            session.get("package")
        ),
    )

    assert session.get(
        "package",
        "",
    ) == ""

print()
print("=" * 72)
print("COMPARISON NO-LOOP TEST COMPLETED")
print("=" * 72)
print(
    "Pricing questions should show prices directly "
    "instead of repeatedly asking coverage/package."
)
