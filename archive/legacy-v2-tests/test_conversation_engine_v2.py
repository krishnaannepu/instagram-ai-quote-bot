import importlib
import sys
import types


# ------------------------------------------------------------------
# External dependency stubs
# ------------------------------------------------------------------

gemini_stub = types.ModuleType("gemini_service")


class CustomerMessageUnderstanding:
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


def get_current_catalogue():
    return {
        "supported_services": ["Wedding", "Birthday"],
        "packages_by_service": {
            "Wedding": ["Basic", "Premium"],
            "Birthday": ["Basic", "Premium"],
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


def answer_business_question(
    question,
    customer_language="English",
    current_conversation=None,
):
    if "difference" in question.lower():
        return GroundedAnswer(
            "Basic gives standard shorter coverage.\n\n"
            "Premium gives longer coverage, enhanced editing, "
            "and priority handling."
        )

    if "which" in question.lower():
        return GroundedAnswer(
            "Basic is the lower-cost option, while Premium gives more "
            "included coverage and priority handling."
        )

    return GroundedAnswer("Confirmed business information response.")


# Mutable handlers configured by each test turn.
_expected_handler = None
_nlu_handler = None


def interpret_expected_field_reply(
    field_name,
    message_text,
    allowed_options=None,
    current_conversation=None,
):
    if _expected_handler is None:
        raise AssertionError("Expected-field handler was not configured")

    return _expected_handler(
        field_name,
        message_text,
        allowed_options or [],
        current_conversation or {},
    )


def understand_customer_message(
    message_text,
    current_conversation=None,
):
    if _nlu_handler is None:
        raise AssertionError("NLU handler was not configured")

    return _nlu_handler(
        message_text,
        current_conversation or {},
    )


gemini_stub.CustomerMessageUnderstanding = CustomerMessageUnderstanding
gemini_stub.get_current_catalogue = get_current_catalogue
gemini_stub.answer_business_question = answer_business_question
gemini_stub.interpret_expected_field_reply = interpret_expected_field_reply
gemini_stub.understand_customer_message = understand_customer_message
sys.modules["gemini_service"] = gemini_stub


quote_stub = types.ModuleType("quote_service")

PRICING = {
    ("Wedding", "Basic"): {
        "included": 4,
        "photo": 500,
        "video": 650,
        "both": 950,
        "extra": 80,
    },
    ("Wedding", "Premium"): {
        "included": 6,
        "photo": 700,
        "video": 850,
        "both": 1200,
        "extra": 100,
    },
}


def calculate_quote(session):
    row = PRICING[(session["service"], session["package"])]
    coverage = session["coverage_type"]
    base = {
        "Photography": row["photo"],
        "Videography": row["video"],
        "Both": row["both"],
    }[coverage]
    duration = float(session.get("duration_hours") or 0)
    extra_hours = max(0, duration - row["included"])
    extra_cost = extra_hours * row["extra"]
    travel_fee = 0

    return {
        "service": session["service"],
        "package": session["package"],
        "coverage_type": coverage,
        "included_hours": row["included"],
        "duration_hours": duration,
        "base_price": base,
        "extra_hours": extra_hours,
        "extra_hour_rate": row["extra"],
        "extra_hours_cost": extra_cost,
        "travel_fee": travel_fee,
        "quote_total": base + extra_cost + travel_fee,
        "status": "QUOTE_READY",
        "human_handoff": False,
    }


quote_stub.calculate_quote = calculate_quote
sys.modules["quote_service"] = quote_stub


engine = importlib.import_module("conversation_engine")


# ------------------------------------------------------------------
# Test helpers
# ------------------------------------------------------------------

def expected(decision, value=None, language="English"):
    return types.SimpleNamespace(
        decision=decision,
        normalized_value=value,
        language=language,
    )


def nlu(**kwargs):
    return CustomerMessageUnderstanding(**kwargs)


def set_expected(handler):
    global _expected_handler
    _expected_handler = handler


def set_nlu(handler):
    global _nlu_handler
    _nlu_handler = handler


def base_session():
    return {
        "sender_id": "customer-1",
        "recipient_id": "business-1",
        "current_stage": "AI_QUOTE",
        "selected_action": "GET_QUOTE",
        "service": "Wedding",
        "package": "Basic",
        "coverage_type": "",
        "travel_required": "",
        "duration_hours": "",
        "event_date": "",
        "location": "",
        "special_requirements": "",
        "quote_data": {},
        "deferred_quote_fields": [],
        "deferred_review_pending": False,
        "deferred_review_active": False,
        "package_reconfirmation_pending": False,
        "package_reconfirmation_current": "",
        "package_reconfirmation_resume_field": "",
        "flow_state": "QUOTE_COVERAGE",
        "expected_quote_field": "coverage_type",
        "resume_stack": [],
        "transition_log": [],
        "status": "ACTIVE",
    }


# ------------------------------------------------------------------
# Scenario A: package comparison interrupt -> side price question -> switch
# ------------------------------------------------------------------

session = base_session()


def coverage_question_interrupt(field, message, options, context):
    assert field == "coverage_type"
    return expected("GENERAL_NLU", language="Hinglish")


def comparison_nlu(message, context):
    return nlu(
        intent="BUSINESS_QUESTION",
        language="Hinglish",
        business_question="Basic aur Premium mein difference kya hai?",
        business_question_type="PACKAGE_COMPARISON",
        requested_packages=["Basic", "Premium"],
    )


set_expected(coverage_question_interrupt)
set_nlu(comparison_nlu)

result = engine.process_ai_customer_message(
    session,
    "Wait basic and premium difference kya hai",
)

assert result["action"] == "ANSWER_BUSINESS_QUESTION"
assert session["package"] == "Basic"
assert session["flow_state"] == "PACKAGE_RECONFIRMATION"
assert session["resume_stack"] == ["QUOTE_COVERAGE"]
assert result["resume_prompt"]["action"] == "RECONFIRM_PACKAGE_SELECTION"
assert result["resume_prompt"]["current_value"] == "Basic"

print("PASS 1 - comparison becomes an interrupt; Basic remains selected")


# Side price question must answer then return to the same package decision.
def reconfirm_general(field, message, options, context):
    assert field == "package_reconfirmation"
    return expected("GENERAL_NLU")


def pricing_nlu(message, context):
    return nlu(
        intent="BUSINESS_QUESTION",
        language="English",
        business_question="What are the prices?",
        business_question_type="PACKAGE_PRICING_COMPARISON",
        requested_packages=["Basic", "Premium"],
    )


set_expected(reconfirm_general)
set_nlu(pricing_nlu)

result = engine.process_ai_customer_message(
    session,
    "Prices??",
)

assert result["action"] == "ANSWER_BUSINESS_QUESTION"
assert "Basic" in result["answer_text"]
assert "Premium" in result["answer_text"]
assert session["flow_state"] == "PACKAGE_RECONFIRMATION"
assert result["resume_prompt"]["action"] == "RECONFIRM_PACKAGE_SELECTION"

print("PASS 2 - side price question returns to pending package decision")


# Acknowledgement remains in reconfirmation.
def reconfirm_pause(field, message, options, context):
    return expected("PAUSE")


set_expected(reconfirm_pause)
result = engine.process_ai_customer_message(session, "Hmm")
assert result["action"] == "WAIT_FOR_PACKAGE_RECONFIRMATION"
assert session["flow_state"] == "PACKAGE_RECONFIRMATION"

print("PASS 3 - Hmm/Okay cannot accidentally leave package reconfirmation")


# Switch to Premium and resume coverage.
def reconfirm_premium(field, message, options, context):
    return expected("VALUE", "Premium", "Hinglish")


set_expected(reconfirm_premium)
result = engine.process_ai_customer_message(session, "Premium kardo")
assert session["package"] == "Premium"
assert session["flow_state"] == "QUOTE_COVERAGE"
assert result["action"] == "ASK_FOR_FIELD"
assert result["next_field"] == "coverage_type"

print("PASS 4 - package switch resumes exactly at coverage")


# ------------------------------------------------------------------
# Scenario B: coverage -> uncertain travel -> deferred review -> final quote
# ------------------------------------------------------------------

def coverage_both(field, message, options, context):
    assert field == "coverage_type"
    return expected("VALUE", "Both")


set_expected(coverage_both)
result = engine.process_ai_customer_message(session, "both")
assert session["coverage_type"] == "Both"
assert session["flow_state"] == "QUOTE_TRAVEL"
assert result["next_field"] == "travel_required"

print("PASS 5 - bare 'both' is coverage, not a pricing continuation")


def travel_maybe(field, message, options, context):
    assert field == "travel_required"
    return expected("UNCLEAR")


set_expected(travel_maybe)
result = engine.process_ai_customer_message(session, "maybe")
assert "travel_required" in session["deferred_quote_fields"]
assert session["flow_state"] == "QUOTE_DURATION"
assert result["next_field"] == "duration_hours"

print("PASS 6 - uncertain travel is deferred instead of looping")


def duration_8(field, message, options, context):
    assert field == "duration_hours"
    return expected("VALUE", "8")


set_expected(duration_8)
result = engine.process_ai_customer_message(session, "8 hours")
assert session["duration_hours"] == 8
assert session["flow_state"] == "QUOTE_DATE"


def date_value(field, message, options, context):
    assert field == "event_date"
    return expected("VALUE", "12 October")


set_expected(date_value)
result = engine.process_ai_customer_message(session, "12 October")
assert session["event_date"] == "12 October"
assert session["flow_state"] == "QUOTE_LOCATION"


def location_value(field, message, options, context):
    assert field == "location"
    return expected("VALUE", "Birmingham")


set_expected(location_value)
result = engine.process_ai_customer_message(session, "Birmingham")
assert result["action"] == "REVIEW_DEFERRED_FIELDS"
assert session["flow_state"] == "DEFERRED_REVIEW_READY"
assert result["deferred_fields"] == ["travel_required"]

print("PASS 7 - end-of-flow checkpoint knows exactly which field is unresolved")


# Natural 'okay kardo' at readiness means proceed.
def review_ready(field, message, options, context):
    assert field == "deferred_review_ready"
    return expected("VALUE", "Yes", "Hinglish")


set_expected(review_ready)
result = engine.process_ai_customer_message(session, "okay kardo")
assert result["action"] == "START_DEFERRED_REVIEW"
assert result["next_field"] == "travel_required"
assert session["flow_state"] == "QUOTE_TRAVEL"

print("PASS 8 - 'okay kardo' starts deferred review")


# Same natural phrase answers the actual binary travel field as Yes.
def travel_yes(field, message, options, context):
    assert field == "travel_required"
    return expected("VALUE", "Yes", "Hinglish")


set_expected(travel_yes)
result = engine.process_ai_customer_message(session, "okay kardo")
assert result["action"] == "READY_FOR_QUOTE"
assert session["travel_required"] == "Yes"
assert session["flow_state"] == "QUOTE_READY"

print("PASS 9 - binary semantics resolve travel and complete the quote")


# ------------------------------------------------------------------
# Scenario C: state safety - contextual repeated fields cannot mutate quote
# ------------------------------------------------------------------

safe_session = {
    **base_session(),
    "coverage_type": "Both",
    "travel_required": "",
    "duration_hours": 8,
    "event_date": "12 October",
    "location": "Birmingham",
    "flow_state": "QUOTE_TRAVEL",
    "expected_quote_field": "travel_required",
}


def travel_to_full_nlu(field, message, options, context):
    return expected("GENERAL_NLU")


def travel_update_nlu(message, context):
    return nlu(
        intent="UPDATE_QUOTE",
        language="English",
        fields_to_update=["travel_required"],
        travel_required="No",
        # Deliberately repeated/reformatted context that MUST NOT be applied.
        event_date="12October",
    )


set_expected(travel_to_full_nlu)
set_nlu(travel_update_nlu)
result = engine.process_ai_customer_message(safe_session, "travel no")
assert safe_session["travel_required"] == "No"
assert safe_session["event_date"] == "12 October"
assert result["action"] == "READY_FOR_QUOTE"

print("PASS 10 - fields_to_update is authoritative; old date cannot be rewritten")


# ------------------------------------------------------------------
# Scenario D: combined difference + pricing returns both kinds of information
# ------------------------------------------------------------------

combined_session = base_session()
combined_session["package"] = ""
combined_session["flow_state"] = "QUOTE_PACKAGE"
combined_session["expected_quote_field"] = "package"


def package_question(field, message, options, context):
    return expected("GENERAL_NLU")


def combined_nlu(message, context):
    return nlu(
        intent="BUSINESS_QUESTION",
        language="English",
        business_question=(
            "What is the difference between Basic and Premium and what are "
            "their prices?"
        ),
        business_question_type="PACKAGE_COMPARISON_WITH_PRICING",
        requested_packages=["Basic", "Premium"],
    )


set_expected(package_question)
set_nlu(combined_nlu)
result = engine.process_ai_customer_message(
    combined_session,
    "difference and prices?",
)
assert "standard shorter coverage" in result["answer_text"]
assert "Pricing" in result["answer_text"]
assert "Photography: £500.00" in result["answer_text"]
assert result["resume_prompt"]["next_field"] == "package"

print("PASS 11 - combined difference + pricing answers both requests")


# ------------------------------------------------------------------
# Scenario E: post-quote change remains deterministic and recalculable
# ------------------------------------------------------------------

post_quote = {
    **safe_session,
    "package": "Premium",
    "travel_required": "Yes",
    "flow_state": "QUOTE_READY",
    "expected_quote_field": "",
    "quote_data": {"quote_total": 1400},
}


def post_quote_update_nlu(message, context):
    return nlu(
        intent="UPDATE_QUOTE",
        language="English",
        fields_to_update=["package"],
        package="Basic",
    )


set_nlu(post_quote_update_nlu)
result = engine.process_ai_customer_message(post_quote, "actually Basic kardo")
assert post_quote["package"] == "Basic"
assert post_quote["quote_data"] == {}
assert result["action"] == "READY_FOR_QUOTE"
assert post_quote["flow_state"] == "QUOTE_READY"

print("PASS 12 - post-quote package change invalidates stale quote and recalculates")


print()
print("=" * 72)
print("CONVERSATION ENGINE V2 REGRESSION SUITE PASSED")
print("=" * 72)
