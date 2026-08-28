import sys
import types

gemini_stub = types.ModuleType(
    "gemini_service"
)

class CustomerMessageUnderstanding:
    pass


class DummyUnderstanding:
    def __init__(
        self,
        **kwargs,
    ):
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

        defaults.update(
            kwargs
        )

        for key, value in defaults.items():
            setattr(
                self,
                key,
                value,
            )

    def model_dump(self):
        return dict(
            self.__dict__
        )


def catalogue():
    return {
        "supported_services": [
            "Wedding",
        ],
        "packages_by_service": {
            "Wedding": [
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


class Answer:
    answer_found = True
    answer_text = (
        "Basic includes shorter coverage.\\n\\n"
        "Premium includes longer coverage."
    )
    should_offer_human = False


def answer_business_question(
    *args,
    **kwargs,
):
    return Answer()


def unused(
    *args,
    **kwargs,
):
    raise AssertionError(
        "Unexpected external dependency call."
    )


gemini_stub.CustomerMessageUnderstanding = (
    CustomerMessageUnderstanding
)
gemini_stub.get_current_catalogue = catalogue
gemini_stub.answer_business_question = (
    answer_business_question
)
gemini_stub.interpret_expected_field_reply = unused
gemini_stub.understand_customer_message = unused

sys.modules[
    "gemini_service"
] = gemini_stub


quote_stub = types.ModuleType(
    "quote_service"
)

quote_stub.calculate_quote = unused

sys.modules[
    "quote_service"
] = quote_stub


import ai_conversation_service as svc


session = {
    "service": "Wedding",
    "package": "Premium",
    "coverage_type": "",
    "travel_required": "",
    "duration_hours": "",
    "event_date": "",
    "location": "",
    "quote_data": {},
    "status": "ACTIVE",
    "selected_action": "GET_QUOTE",
    "expected_quote_field": "",
    "deferred_quote_fields": [],
    "deferred_review_pending": False,
    "deferred_review_active": False,
    "package_reconfirmation_pending": True,
    "package_reconfirmation_current": "Premium",
    "package_reconfirmation_resume_field": "coverage_type",
    "last_business_question_type": "PACKAGE_COMPARISON",
    "last_business_question_packages": [
        "Basic",
        "Premium",
    ],
}


# --------------------------------------------------------------
# TEST 1: side pricing question keeps package decision pending.
# --------------------------------------------------------------

def reconfirm_general_nlu(
    *args,
    **kwargs,
):
    return types.SimpleNamespace(
        decision="GENERAL_NLU",
        normalized_value=None,
        language="English",
    )


def nlu_prices(
    *args,
    **kwargs,
):
    return DummyUnderstanding(
        intent="BUSINESS_QUESTION",
        business_question="Prices?",
        business_question_type=
            "PACKAGE_PRICING_COMPARISON",
        requested_packages=[
            "Basic",
            "Premium",
        ],
    )


svc.interpret_expected_field_reply = (
    reconfirm_general_nlu
)
svc.understand_customer_message = (
    nlu_prices
)

# Keep the test independent from the real quote engine.
svc._is_package_pricing_continuation = (
    lambda session, message_text: False
)

svc._build_package_price_comparison = (
    lambda session, requested_packages: {
        "answer_found": True,
        "answer_text": (
            "Basic £500.\\n\\nPremium £700."
        ),
        "should_offer_human": False,
        "comparison_quotes": [],
        "comparison_missing_field": None,
        "comparison_mode": "CATALOGUE_PRICING",
    }
)

result = svc.process_ai_customer_message(
    session,
    "Prices??",
)

print("=" * 72)
print("SIDE PRICE QUESTION")
print("=" * 72)
print("ACTION:", result["action"])
print(
    "PENDING:",
    session["package_reconfirmation_pending"],
)

assert (
    result["action"]
    == "ANSWER_BUSINESS_QUESTION"
)
assert (
    session["package_reconfirmation_pending"]
    is True
)
assert (
    session["package"]
    == "Premium"
)


# --------------------------------------------------------------
# TEST 2: "Hmm" reaching full NLU as OTHER must remain in package
# reconfirmation instead of becoming CLARIFY.
# --------------------------------------------------------------

def nlu_other(
    *args,
    **kwargs,
):
    return DummyUnderstanding(
        intent="OTHER",
        language="English",
    )


svc.understand_customer_message = (
    nlu_other
)

result = svc.process_ai_customer_message(
    session,
    "Hmm",
)

print()
print("=" * 72)
print("HMM / ACKNOWLEDGEMENT")
print("=" * 72)
print("ACTION:", result["action"])
print(
    "CURRENT PACKAGE:",
    result["current_package"],
)

assert (
    result["action"]
    == "WAIT_FOR_PACKAGE_RECONFIRMATION"
)
assert (
    result["current_package"]
    == "Premium"
)


# --------------------------------------------------------------
# TEST 3: "Okay" classified as PAUSE stays in reconfirmation.
# --------------------------------------------------------------

def reconfirm_pause(
    *args,
    **kwargs,
):
    return types.SimpleNamespace(
        decision="PAUSE",
        normalized_value=None,
        language="English",
    )


svc.interpret_expected_field_reply = (
    reconfirm_pause
)

result = svc.process_ai_customer_message(
    session,
    "Okay",
)

print()
print("=" * 72)
print("OKAY / PAUSE")
print("=" * 72)
print("ACTION:", result["action"])

assert (
    result["action"]
    == "WAIT_FOR_PACKAGE_RECONFIRMATION"
)


# --------------------------------------------------------------
# TEST 4: clear switch still resumes interrupted coverage field.
# --------------------------------------------------------------

def reconfirm_basic(
    *args,
    **kwargs,
):
    return types.SimpleNamespace(
        decision="VALUE",
        normalized_value="Basic",
        language="English",
    )


svc.interpret_expected_field_reply = (
    reconfirm_basic
)

result = svc.process_ai_customer_message(
    session,
    "switch to Basic",
)

print()
print("=" * 72)
print("PACKAGE DECISION")
print("=" * 72)
print(
    "PACKAGE:",
    session["package"],
)
print(
    "NEXT:",
    result["next_field"],
)

assert (
    session["package"]
    == "Basic"
)
assert (
    session["package_reconfirmation_pending"]
    is False
)
assert (
    result["next_field"]
    == "coverage_type"
)

print()
print("=" * 72)
print(
    "PACKAGE STATE LOOP REGRESSION TEST PASSED"
)
print("=" * 72)
