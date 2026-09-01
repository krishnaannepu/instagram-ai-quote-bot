import sys
import types

gemini_stub = types.ModuleType("gemini_service")

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
        "supported_services": ["Birthday"],
        "packages_by_service": {
            "Birthday": ["Basic", "Premium"],
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
        "Basic includes up to 3 hours with standard editing.\n\n"
        "Premium includes up to 4 hours with enhanced editing "
        "and priority handling."
    )
    should_offer_human = False


def answer_business_question(*args, **kwargs):
    return Answer()


def unused(*args, **kwargs):
    raise AssertionError("Unexpected dependency call")


gemini_stub.CustomerMessageUnderstanding = CustomerMessageUnderstanding
gemini_stub.get_current_catalogue = catalogue
gemini_stub.answer_business_question = answer_business_question
gemini_stub.interpret_expected_field_reply = unused
gemini_stub.understand_customer_message = unused
sys.modules["gemini_service"] = gemini_stub

quote_stub = types.ModuleType("quote_service")
quote_stub.calculate_quote = unused
sys.modules["quote_service"] = quote_stub

import ai_conversation_service as svc

session = {
    "service": "Birthday",
    "package": "Basic",
    "coverage_type": "",
    "travel_required": "",
    "duration_hours": "",
    "event_date": "",
    "location": "",
    "quote_data": {},
    "status": "ACTIVE",
    "selected_action": "GET_QUOTE",
    "expected_quote_field": "coverage_type",
    "deferred_quote_fields": [],
    "deferred_review_pending": False,
    "deferred_review_active": False,
    "package_reconfirmation_pending": False,
    "package_reconfirmation_current": "",
    "package_reconfirmation_resume_field": "",
    "last_business_question_type": "",
    "last_business_question_packages": [],
}

def field_general(*args, **kwargs):
    return types.SimpleNamespace(
        decision="GENERAL_NLU",
        normalized_value=None,
        language="Hinglish",
    )

def nlu_comparison(*args, **kwargs):
    return DummyUnderstanding(
        intent="BUSINESS_QUESTION",
        language="Hinglish",
        business_question="Basic aur Premium mein difference kya hai?",
        business_question_type="PACKAGE_COMPARISON",
        requested_packages=["Basic", "Premium"],
    )

svc.interpret_expected_field_reply = field_general
svc.understand_customer_message = nlu_comparison

result = svc.process_ai_customer_message(
    session,
    "Wait basic and premium difference kya hi",
)

print("=" * 72)
print("AFTER COMPARISON")
print("=" * 72)
print("ACTION:", result["action"])
print("PACKAGE:", session["package"])
print("PENDING:", session["package_reconfirmation_pending"])
print("RESUME:", session["package_reconfirmation_resume_field"])

assert result["action"] == "ANSWER_BUSINESS_QUESTION_AND_RECONFIRM_PACKAGE"
assert session["package"] == "Basic"
assert session["package_reconfirmation_pending"] is True
assert session["package_reconfirmation_current"] == "Basic"
assert session["package_reconfirmation_resume_field"] == "coverage_type"
assert session["expected_quote_field"] == ""

def pause_reconfirm(*args, **kwargs):
    return types.SimpleNamespace(
        decision="PAUSE",
        normalized_value=None,
        language="English",
    )

svc.interpret_expected_field_reply = pause_reconfirm

result = svc.process_ai_customer_message(
    session,
    "Okay",
)

print()
print("BARE OKAY ACTION:", result["action"])
assert result["action"] == "WAIT_FOR_PACKAGE_RECONFIRMATION"
assert session["package"] == "Basic"

def switch_premium(*args, **kwargs):
    return types.SimpleNamespace(
        decision="VALUE",
        normalized_value="Premium",
        language="Hinglish",
    )

svc.interpret_expected_field_reply = switch_premium

result = svc.process_ai_customer_message(
    session,
    "Premium kardo",
)

print()
print("SWITCH ACTION:", result["action"])
print("PACKAGE:", session["package"])
print("NEXT:", result["next_field"])

assert session["package"] == "Premium"
assert session["package_reconfirmation_pending"] is False
assert result["action"] == "ASK_FOR_FIELD"
assert result["next_field"] == "coverage_type"

# Keep-current branch.
session["package"] = "Basic"
session["package_reconfirmation_pending"] = True
session["package_reconfirmation_current"] = "Basic"
session["package_reconfirmation_resume_field"] = "coverage_type"
session["expected_quote_field"] = ""

def keep_basic(*args, **kwargs):
    return types.SimpleNamespace(
        decision="VALUE",
        normalized_value="Basic",
        language="English",
    )

svc.interpret_expected_field_reply = keep_basic

result = svc.process_ai_customer_message(
    session,
    "continue with basic",
)

print()
print("KEEP PACKAGE:", session["package"])
print("NEXT:", result["next_field"])

assert session["package"] == "Basic"
assert session["package_reconfirmation_pending"] is False
assert result["next_field"] == "coverage_type"

print()
print("=" * 72)
print("PACKAGE RECONFIRMATION REGRESSION TEST PASSED")
print("=" * 72)
