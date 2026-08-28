import os
import sys
import types

from dotenv import load_dotenv


# ------------------------------------------------------------------
# Load local environment
# ------------------------------------------------------------------

load_dotenv()

customer_email = os.getenv(
    "TEST_CUSTOMER_EMAIL",
    "",
).strip().lower()

if not customer_email:
    customer_email = input(
        "Enter the customer email address for this test: "
    ).strip().lower()

if not customer_email:
    raise ValueError(
        "Customer email is required."
    )


# ------------------------------------------------------------------
# Bypass Google Sheets / Gemini / Instagram imports for this test
# ------------------------------------------------------------------

fake_sheets = types.ModuleType("sheets_service")
fake_sheets.persist_completed_quote = lambda *args, **kwargs: {}
fake_sheets.save_completed_lead = lambda *args, **kwargs: {}
fake_sheets.update_lead = lambda *args, **kwargs: {}
fake_sheets.get_pricing_rule = lambda *args, **kwargs: {}
sys.modules["sheets_service"] = fake_sheets

fake_ai = types.ModuleType("ai_conversation_service")
fake_ai.get_available_options_for_field = lambda *args, **kwargs: []
fake_ai.get_next_missing_quote_field = lambda *args, **kwargs: None
fake_ai.get_supported_services = lambda *args, **kwargs: []
fake_ai.process_ai_customer_message = lambda *args, **kwargs: {}
sys.modules["ai_conversation_service"] = fake_ai

fake_gemini = types.ModuleType("gemini_service")
fake_gemini.generate_conversation_reply = lambda *args, **kwargs: ""
sys.modules["gemini_service"] = fake_gemini

fake_instagram = types.ModuleType("instagram_service")
fake_instagram.send_instagram_menu = lambda *args, **kwargs: None
sys.modules["instagram_service"] = fake_instagram


# ------------------------------------------------------------------
# Import the REAL local files we actually want to test
# ------------------------------------------------------------------

import main
from email_service import send_new_lead_email


# ------------------------------------------------------------------
# Test quote
# ------------------------------------------------------------------

quote = {
    "service": "Wedding",
    "package": "Premium",
    "coverage_type": "Both",
    "included_hours": 6.0,
    "duration_hours": 8.0,
    "base_price": 1200.0,
    "extra_hours": 2.0,
    "extra_hour_rate": 100.0,
    "extra_hours_cost": 200.0,
    "travel_fee": 0.0,
    "quote_total": 1400.0,
    "status": "QUOTE_READY",
    "human_handoff": False,
}

lead = {
    "lead_id": "LOCAL-FINAL-QUOTE-TEST",
}

session = {
    "sender_id": "LOCAL_CUSTOMER",
    "recipient_id": "LOCAL_BUSINESS",
    "current_stage": "POST_QUOTE_OPTIONS",
    "selected_action": "GET_QUOTE",
    "service": "Wedding",
    "package": "Premium",
    "coverage_type": "Both",
    "travel_required": "No",
    "duration_hours": 8,
    "event_date": "12 October",
    "location": "Birmingham",
    "customer_email": customer_email,
    "quote_email_sent": False,
    "customer_phone": "",
    "callback_preference": "",
    "handoff_requested": "",
    "handoff_requested_at": "",
    "handoff_status": "",
    "human_handoff": False,
    "active_lead_id": lead["lead_id"],
    "quote_data": quote,
    "lead_data": lead,
    "status": "QUOTE_READY",
    "last_message_id": "LOCAL_TEST_001",
}


# ------------------------------------------------------------------
# Stop main.py from touching Sheets during handoff
# ------------------------------------------------------------------

def fake_ensure_active_lead(session: dict):
    session["active_lead_id"] = lead["lead_id"]
    session["lead_data"] = lead
    return lead


def fake_update_active_lead(session: dict, updates: dict):
    session["lead_data"] = {
        **lead,
        **updates,
    }
    return session["lead_data"]


main.ensure_active_lead = fake_ensure_active_lead
main.update_active_lead = fake_update_active_lead


# ------------------------------------------------------------------
# Force CLOSED office hours
# ------------------------------------------------------------------

main.is_office_open = lambda: False


# ------------------------------------------------------------------
# TEST 1 - Friend receives calculation email
# ------------------------------------------------------------------

print()
print("=" * 72)
print("TEST 1 - FRIEND / BUSINESS OWNER QUOTE EMAIL")
print("=" * 72)

owner_result = send_new_lead_email(
    session=session,
    quote=quote,
    lead=lead,
)

print("PASS - owner quote email sent")
print("Message ID:", owner_result.get("id"))
print()
print("Expected section:")
print("Calculations Involved")
print("Extra Hours = max(8 - 6, 0) = 2")
print("Extra Hours Cost = 2 × £100.00 = £200.00")
print(
    "Final Quote = "
    "£1,200.00 + £200.00 + £0.00 = £1,400.00"
)


# ------------------------------------------------------------------
# TEST 2 - main.py closed-hours Speak to Team
# ------------------------------------------------------------------

print()
print("=" * 72)
print("TEST 2 - MAIN.PY CLOSED-HOURS SPEAK TO TEAM")
print("=" * 72)

handoff_menu = main.process_handoff_request(
    session=session,
)

print("PASS - main.py handoff completed")
print()
print("Instagram message returned:")
print(handoff_menu.get("message", ""))
print()
print(
    "quote_email_sent:",
    session.get("quote_email_sent"),
)
print(
    "customer_email:",
    session.get("customer_email"),
)


# ------------------------------------------------------------------
# Expected result
# ------------------------------------------------------------------

print()
print("=" * 72)
print("FINAL RESULT")
print("=" * 72)

print(
    "Expected emails:"
)
print(
    "1. Friend/business owner -> quote email with calculation formula."
)
print(
    "2. Friend/business owner -> Priority Instagram Handoff email."
)
print(
    "3. Customer -> ACTUAL final calculated quote email for £1,400."
)
print()
print(
    "The customer email must contain:"
)
print(
    "Base Price: £1,200.00"
)
print(
    "Included Hours: 6"
)
print(
    "Requested Hours: 8"
)
print(
    "Extra Hours Cost: £200.00"
)
print(
    "Travel Fee: £0.00"
)
print(
    "Estimated Total: £1,400.00"
)
