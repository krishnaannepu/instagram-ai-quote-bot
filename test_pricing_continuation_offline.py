import ai_conversation_service as svc


def fail_if_gemini_is_called(*args, **kwargs):
    raise AssertionError(
        "Gemini NLU should NOT be called for this deterministic "
        "package-pricing continuation."
    )


# Simulate the exact state after the customer has been discussing
# Basic and Premium packages.
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

# If our deterministic bypass works, this function will never run.
svc.understand_customer_message = (
    fail_if_gemini_is_called
)

print("=" * 72)
print("TURN 1 - PAISA??")
print("=" * 72)

result = svc.process_ai_customer_message(
    session,
    "Paisa??",
)

print("ACTION:", result.get("action"))
print(
    "QUESTION TYPE:",
    result.get("business_question_type"),
)
print(
    "MODE:",
    result.get("comparison_mode"),
)
print("ANSWER:")
print(result.get("answer_text"))
print(
    "PACKAGE AFTER:",
    repr(session.get("package")),
)

assert result["action"] == "ANSWER_BUSINESS_QUESTION"
assert (
    result["business_question_type"]
    == "PACKAGE_PRICING_COMPARISON"
)
assert result["comparison_mode"] == "CATALOGUE_PRICING"
assert "Basic" in result["answer_text"]
assert "Premium" in result["answer_text"]
assert "Photography:" in result["answer_text"]
assert "Videography:" in result["answer_text"]
assert "Both:" in result["answer_text"]
assert session["package"] == ""

print()
print("=" * 72)
print("TURN 2 - COMPARE SEPARATELY")
print("=" * 72)

result = svc.process_ai_customer_message(
    session,
    "Compare separately",
)

print("ACTION:", result.get("action"))
print(
    "QUESTION TYPE:",
    result.get("business_question_type"),
)
print(
    "MODE:",
    result.get("comparison_mode"),
)
print("ANSWER:")
print(result.get("answer_text"))
print(
    "PACKAGE AFTER:",
    repr(session.get("package")),
)

assert result["comparison_mode"] == "CATALOGUE_PRICING"
assert session["package"] == ""

print()
print("=" * 72)
print("DETERMINISTIC PRICING CONTINUATION TEST PASSED")
print("=" * 72)
print(
    "Gemini was deliberately disabled in this test."
)
