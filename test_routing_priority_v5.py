import sys
import types

gemini_stub = types.ModuleType(
    "gemini_service"
)

class CustomerMessageUnderstanding:
    pass


class DummyUnderstanding:
    def __init__(self, **kwargs):
        defaults = {
            "intent": "OTHER",
            "language": "English",
            "fields_to_update": [],
            "service": None,
            "requested_service_text": None,
            "package": None,
            "coverage_type": None,
            "travel_required": None,
            "duration_hours": None,
            "event_date": None,
            "location": None,
            "business_question": None,
            "business_question_type": "GENERAL",
            "requested_packages": [],
            "special_requirements": None,
            "needs_clarification": False,
        }
        defaults.update(kwargs)

        for key, value in defaults.items():
            setattr(self, key, value)

    def model_dump(self):
        return dict(self.__dict__)


def catalogue():
    return {
        "supported_services": [
            "Wedding",
            "Birthday",
        ],
        "packages_by_service": {
            "Wedding": [
                "Basic",
                "Premium",
            ],
            "Birthday": [
                "Basic",
                "Premium",
            ],
        },
        "coverage_types": [
            "Photography",
            "Videography",
            "Both",
        ],
    }


class GroundedAnswer:
    def __init__(self, text):
        self.answer_found = True
        self.answer_text = text
        self.should_offer_human = False


def grounded_answer(
    question,
    customer_language,
    current_conversation,
):
    return GroundedAnswer(
        "Basic includes shorter standard coverage."
        "\\n\\n"
        "Premium includes longer coverage, enhanced editing, "
        "and priority handling."
    )


def unused(*args, **kwargs):
    raise AssertionError(
        "Unexpected external dependency call."
    )


gemini_stub.CustomerMessageUnderstanding = (
    CustomerMessageUnderstanding
)
gemini_stub.answer_business_question = grounded_answer
gemini_stub.get_current_catalogue = catalogue
gemini_stub.interpret_expected_field_reply = unused
gemini_stub.understand_customer_message = unused

sys.modules["gemini_service"] = gemini_stub


quote_stub = types.ModuleType(
    "quote_service"
)

PRICES = {
    ("Birthday", "Basic", "Photography"):
        (250, 3, 50),
    ("Birthday", "Basic", "Videography"):
        (300, 3, 50),
    ("Birthday", "Basic", "Both"):
        (450, 3, 50),
    ("Birthday", "Premium", "Photography"):
        (350, 4, 60),
    ("Birthday", "Premium", "Videography"):
        (425, 4, 60),
    ("Birthday", "Premium", "Both"):
        (600, 4, 60),
}


def fake_calculate_quote(session):
    key = (
        session["service"],
        session["package"],
        session["coverage_type"],
    )

    base, included, extra_rate = (
        PRICES[key]
    )

    duration = float(
        session.get(
            "duration_hours",
            1,
        )
        or 1
    )

    extra_hours = max(
        0,
        duration - included,
    )

    extra_cost = (
        extra_hours
        * extra_rate
    )

    return {
        "service":
            session["service"],
        "package":
            session["package"],
        "coverage_type":
            session["coverage_type"],
        "duration_hours":
            duration,
        "included_hours":
            included,
        "base_price":
            base,
        "extra_hours":
            extra_hours,
        "extra_hour_rate":
            extra_rate,
        "extra_hours_cost":
            extra_cost,
        "travel_fee": 0,
        "quote_total":
            base + extra_cost,
    }


quote_stub.calculate_quote = (
    fake_calculate_quote
)

sys.modules["quote_service"] = quote_stub


import ai_conversation_service as svc


session = {
    "service": "Birthday",
    "package": "",
    "coverage_type": "",
    "travel_required": "",
    "duration_hours": "",
    "event_date": "",
    "location": "",
    "quote_data": {},
    "status": "ACTIVE",
    "selected_action": "GET_QUOTE",
    "expected_quote_field": "package",
    "deferred_quote_fields": [],
    "deferred_review_pending": False,
    "deferred_review_active": False,
    "last_business_question_type": "",
    "last_business_question_packages": [],
}


# Test 1: combined difference + prices.
def field_general_nlu(
    field_name,
    message_text,
    allowed_options=None,
    current_conversation=None,
):
    return types.SimpleNamespace(
        decision="GENERAL_NLU",
        normalized_value=None,
        language="English",
    )


def nlu_combined(
    message_text,
    current_conversation=None,
):
    return DummyUnderstanding(
        intent="BUSINESS_QUESTION",
        business_question=(
            "What is the difference between Basic and Premium "
            "and what are their prices?"
        ),
        business_question_type=
            "PACKAGE_COMPARISON_WITH_PRICING",
        requested_packages=[
            "Basic",
            "Premium",
        ],
    )


svc.interpret_expected_field_reply = (
    field_general_nlu
)
svc.understand_customer_message = (
    nlu_combined
)

result = svc.process_ai_customer_message(
    session,
    "what is the difference between both? what are their prices?",
)

print("=" * 72)
print("COMBINED DIFFERENCE + PRICE")
print("=" * 72)
print(result["answer_text"])

assert (
    result["business_question_type"]
    == "PACKAGE_COMPARISON_WITH_PRICING"
)
assert "shorter standard coverage" in result["answer_text"]
assert "longer coverage" in result["answer_text"]
assert "Pricing" in result["answer_text"]
assert "Photography: £250.00" in result["answer_text"]
assert "Both: £600.00" in result["answer_text"]
assert session["package"] == ""


# Test 2: difference-only after prior pricing must not repeat pricing.
session["last_business_question_type"] = (
    "PACKAGE_PRICING_COMPARISON"
)
session["last_business_question_packages"] = [
    "Basic",
    "Premium",
]
session["expected_quote_field"] = ""


def nlu_difference_only(
    message_text,
    current_conversation=None,
):
    return DummyUnderstanding(
        intent="BUSINESS_QUESTION",
        business_question=(
            "What is the difference between Basic and Premium?"
        ),
        business_question_type=
            "PACKAGE_COMPARISON",
        requested_packages=[
            "Basic",
            "Premium",
        ],
    )


svc.understand_customer_message = (
    nlu_difference_only
)

result = svc.process_ai_customer_message(
    session,
    "what's the difference between both?",
)

print()
print("=" * 72)
print("DIFFERENCE ONLY")
print("=" * 72)
print(result["answer_text"])

assert (
    result["business_question_type"]
    == "PACKAGE_COMPARISON"
)
assert "Photography: £" not in result["answer_text"]


# Test 3: actual package selection then coverage "both".
session["expected_quote_field"] = "package"


def package_value(
    field_name,
    message_text,
    allowed_options=None,
    current_conversation=None,
):
    assert field_name == "package"

    return types.SimpleNamespace(
        decision="VALUE",
        normalized_value="Premium",
        language="English",
    )


svc.interpret_expected_field_reply = (
    package_value
)

result = svc.process_ai_customer_message(
    session,
    "do premium",
)

print()
print("=" * 72)
print("PACKAGE SELECTED")
print("=" * 72)
print("PACKAGE:", session["package"])
print("NEXT:", result["next_field"])

assert session["package"] == "Premium"
assert result["next_field"] == "coverage_type"
assert session["last_business_question_type"] == ""
assert session["last_business_question_packages"] == []


def coverage_value(
    field_name,
    message_text,
    allowed_options=None,
    current_conversation=None,
):
    assert field_name == "coverage_type"

    return types.SimpleNamespace(
        decision="VALUE",
        normalized_value="Both",
        language="English",
    )


svc.interpret_expected_field_reply = (
    coverage_value
)

result = svc.process_ai_customer_message(
    session,
    "both",
)

print()
print("=" * 72)
print("COVERAGE SELECTED")
print("=" * 72)
print("COVERAGE:", session["coverage_type"])
print("ACTION:", result["action"])
print("NEXT:", result["next_field"])

assert session["coverage_type"] == "Both"
assert result["action"] == "ASK_FOR_FIELD"
assert result["next_field"] == "travel_required"


# Test 4: bare "both" alone is not a pricing continuation.
assert (
    svc._is_package_pricing_continuation(
        {
            "last_business_question_type":
                "PACKAGE_PRICING_COMPARISON",
            "last_business_question_packages":
                [
                    "Basic",
                    "Premium",
                ],
            "expected_quote_field": "",
        },
        "both",
    )
    is False
)

print()
print("=" * 72)
print("ROUTING PRIORITY REGRESSION TEST PASSED")
print("=" * 72)
