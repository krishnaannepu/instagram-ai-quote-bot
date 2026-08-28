from types import SimpleNamespace

import ai_conversation_service as svc


def fake_interpreter(
    field_name,
    message_text,
    allowed_options=None,
    current_conversation=None,
):
    normalized = message_text.lower().strip()

    table = {
        ("travel_required", "maybe"):
            ("UNCLEAR", None),
        ("duration_hours", "8 hours"):
            ("VALUE", "8"),
        ("event_date", "12 october"):
            ("VALUE", "12 October"),
        ("location", "birmingham"):
            ("VALUE", "Birmingham"),
        ("deferred_review_ready", "haan ready"):
            ("VALUE", "Yes"),
        ("deferred_review_ready", "not now"):
            ("VALUE", "No"),
        ("travel_required", "kavali"):
            ("VALUE", "Yes"),
    }

    decision, value = table[
        (field_name, normalized)
    ]

    return SimpleNamespace(
        decision=decision,
        normalized_value=value,
        language="Multilingual",
    )


svc.interpret_expected_field_reply = fake_interpreter

session = {
    "service": "Wedding",
    "package": "Premium",
    "coverage_type": "Both",
    "travel_required": "",
    "duration_hours": "",
    "event_date": "",
    "location": "",
    "quote_data": {},
    "status": "ACTIVE",
    "selected_action": "GET_QUOTE",
    "expected_quote_field": "travel_required",
    "deferred_quote_fields": [],
    "deferred_review_pending": False,
    "deferred_review_active": False,
}

print("=" * 72)
print("TURN 1 - CUSTOMER IS UNSURE")
print("=" * 72)

result = svc.process_ai_customer_message(
    session,
    "Maybe",
)

print("ACTION:", result["action"])
print("DEFERRED:", session["deferred_quote_fields"])
print("NEXT:", result.get("next_field"))

assert result["action"] == "ASK_FOR_FIELD"
assert result["next_field"] == "duration_hours"
assert session["deferred_quote_fields"] == [
    "travel_required"
]
assert session["travel_required"] == ""

print()
print("=" * 72)
print("TURN 2 - DURATION")
print("=" * 72)

result = svc.process_ai_customer_message(
    session,
    "8 hours",
)

print("ACTION:", result["action"])
print("NEXT:", result.get("next_field"))

assert result["action"] == "ASK_FOR_FIELD"
assert result["next_field"] == "event_date"

print()
print("=" * 72)
print("TURN 3 - DATE")
print("=" * 72)

result = svc.process_ai_customer_message(
    session,
    "12 October",
)

print("ACTION:", result["action"])
print("NEXT:", result.get("next_field"))

assert result["action"] == "ASK_FOR_FIELD"
assert result["next_field"] == "location"

print()
print("=" * 72)
print("TURN 4 - LOCATION / CHECKPOINT")
print("=" * 72)

result = svc.process_ai_customer_message(
    session,
    "Birmingham",
)

print("ACTION:", result["action"])
print("DEFERRED:", result.get("deferred_fields"))
print("STATUS:", session["status"])

assert result["action"] == "REVIEW_DEFERRED_FIELDS"
assert result["deferred_fields"] == [
    "travel_required"
]
assert session["status"] == "AWAITING_DEFERRED_CONFIRMATION"
assert session["deferred_review_pending"] is True

print()
print("=" * 72)
print("TURN 5 - CUSTOMER IS READY")
print("=" * 72)

result = svc.process_ai_customer_message(
    session,
    "haan ready",
)

print("ACTION:", result["action"])
print("NEXT:", result.get("next_field"))
print("REVIEW ACTIVE:", session["deferred_review_active"])

assert result["action"] == "START_DEFERRED_REVIEW"
assert result["next_field"] == "travel_required"
assert session["deferred_review_active"] is True

print()
print("=" * 72)
print("TURN 6 - DEFERRED FIELD CONFIRMED")
print("=" * 72)

result = svc.process_ai_customer_message(
    session,
    "kavali",
)

print("ACTION:", result["action"])
print("TRAVEL:", session["travel_required"])
print("DEFERRED:", session["deferred_quote_fields"])

assert result["action"] == "READY_FOR_QUOTE"
assert session["travel_required"] == "Yes"
assert session["deferred_quote_fields"] == []
assert session["deferred_review_pending"] is False
assert session["deferred_review_active"] is False

print()
print("=" * 72)
print("PAUSE BEHAVIOUR")
print("=" * 72)

pause_session = {
    "service": "Wedding",
    "package": "Premium",
    "coverage_type": "Both",
    "travel_required": "",
    "duration_hours": 8,
    "event_date": "12 October",
    "location": "Birmingham",
    "quote_data": {},
    "status": "AWAITING_DEFERRED_CONFIRMATION",
    "selected_action": "GET_QUOTE",
    "expected_quote_field": "",
    "deferred_quote_fields": [
        "travel_required"
    ],
    "deferred_review_pending": True,
    "deferred_review_active": False,
}

result = svc.process_ai_customer_message(
    pause_session,
    "not now",
)

print("ACTION:", result["action"])
print("STATUS:", pause_session["status"])

assert result["action"] == "DEFERRED_REVIEW_PAUSED"
assert pause_session["status"] == "AWAITING_DEFERRED_CONFIRMATION"

print()
print("=" * 72)
print("DEFERRED REVIEW CHECKPOINT TEST PASSED")
print("=" * 72)
print(
    "Uncertain fields are deferred, the customer is warned before final "
    "quote generation, and only the remaining deferred fields are then "
    "collected."
)
