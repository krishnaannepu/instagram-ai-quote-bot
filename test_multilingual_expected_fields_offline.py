from types import SimpleNamespace

import ai_conversation_service as svc


def fake_interpreter(
    field_name,
    message_text,
    allowed_options=None,
    current_conversation=None,
):
    key = (
        field_name,
        message_text.lower().strip(),
    )

    table = {
        ("package", "premium e kavali"):
            ("VALUE", "Premium"),
        ("coverage_type", "rendu kavali"):
            ("VALUE", "Both"),
        ("travel_required", "vaddu"):
            ("VALUE", "No"),
        ("travel_required", "kavali"):
            ("VALUE", "Yes"),
        ("travel_required", "not at the moment"):
            ("VALUE", "No"),
        ("duration_hours", "8 hours"):
            ("VALUE", "8"),
        ("event_date", "12 october"):
            ("VALUE", "12 October"),
        ("location", "birmingham"):
            ("VALUE", "Birmingham"),
        ("package", "premium ante enti?"):
            ("GENERAL_NLU", None),
        ("travel_required", "maybe"):
            ("UNCLEAR", None),
    }

    decision, value = table[key]

    return SimpleNamespace(
        decision=decision,
        normalized_value=value,
        language="Multilingual",
    )


svc.interpret_expected_field_reply = (
    fake_interpreter
)


def run_value_case(
    field_name,
    message,
    initial_session,
    expected_value,
):
    session = dict(initial_session)
    session["expected_quote_field"] = field_name

    result = svc.process_ai_customer_message(
        session,
        message,
    )

    print("=" * 72)
    print("FIELD:", field_name)
    print("CUSTOMER:", message)
    print("STORED:", session.get(field_name))
    print("ACTION:", result.get("action"))
    print("NEXT:", result.get("next_field"))

    assert session[field_name] == expected_value
    assert result["action"] in {
        "ASK_FOR_FIELD",
        "READY_FOR_QUOTE",
    }


base = {
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
}

run_value_case(
    "package",
    "premium e kavali",
    base,
    "Premium",
)

package_done = {
    **base,
    "package": "Premium",
}

run_value_case(
    "coverage_type",
    "rendu kavali",
    package_done,
    "Both",
)

coverage_done = {
    **package_done,
    "coverage_type": "Both",
}

run_value_case(
    "travel_required",
    "vaddu",
    coverage_done,
    "No",
)

run_value_case(
    "travel_required",
    "kavali",
    coverage_done,
    "Yes",
)

run_value_case(
    "travel_required",
    "not at the moment",
    coverage_done,
    "No",
)

travel_done = {
    **coverage_done,
    "travel_required": "No",
}

run_value_case(
    "duration_hours",
    "8 hours",
    travel_done,
    8,
)

duration_done = {
    **travel_done,
    "duration_hours": 8,
}

run_value_case(
    "event_date",
    "12 October",
    duration_done,
    "12 October",
)

date_done = {
    **duration_done,
    "event_date": "12 October",
}

run_value_case(
    "location",
    "Birmingham",
    date_done,
    "Birmingham",
)


# UNCLEAR must simply ask the same field again, not hand off to a human.
session = dict(coverage_done)
session["expected_quote_field"] = "travel_required"

result = svc.process_ai_customer_message(
    session,
    "maybe",
)

assert result["action"] == "ASK_FOR_FIELD"
assert result["next_field"] == "travel_required"
assert result.get("clarification") is True


# GENERAL_NLU must fall through rather than selecting the mentioned package.
def fail_full_nlu_with_marker(
    message_text,
    current_conversation=None,
):
    raise RuntimeError(
        "FULL_NLU_REACHED"
    )


svc.understand_customer_message = (
    fail_full_nlu_with_marker
)

session = dict(base)
session["expected_quote_field"] = "package"

try:
    svc.process_ai_customer_message(
        session,
        "premium ante enti?",
    )
except RuntimeError as exc:
    assert str(exc) == "FULL_NLU_REACHED"
else:
    raise AssertionError(
        "Package question should have fallen through to full NLU."
    )

assert session["package"] == ""

print()
print("=" * 72)
print("MULTILINGUAL EXPECTED-FIELD ROUTING TEST PASSED")
print("=" * 72)
print(
    "Clear natural-language replies update the expected field; "
    "questions still fall through to normal NLU; unclear replies "
    "ask for clarification without human handoff."
)
