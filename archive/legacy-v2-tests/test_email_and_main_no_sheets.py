import os
import sys
import types

from dotenv import load_dotenv

from email_service import (
    send_customer_quote_email,
    send_new_lead_email,
)


# ------------------------------------------------------------------
# Environment
# ------------------------------------------------------------------

load_dotenv()

customer_email = os.getenv(
    "TEST_CUSTOMER_EMAIL",
    "",
).strip().lower()

if not customer_email:
    customer_email = input(
        "Enter the email address to use as the test customer: "
    ).strip().lower()

if not customer_email:
    raise ValueError(
        "A test customer email address is required."
    )


# ------------------------------------------------------------------
# Fixed local quote data
# ------------------------------------------------------------------

session = {
    "sender_id": "LOCAL_EMAIL_TEST_CUSTOMER",
    "recipient_id": "LOCAL_EMAIL_TEST_BUSINESS",
    "current_stage": "ASK_EMAIL_CONFIRMATION",
    "selected_action": "GET_QUOTE",
    "service": "Wedding",
    "package": "Premium",
    "coverage_type": "Both",
    "travel_required": "No",
    "duration_hours": 8,
    "event_date": "12 October",
    "location": "Birmingham",
    "customer_email": customer_email,
    "customer_phone": "",
    "callback_preference": "",
    "handoff_requested": "",
    "handoff_requested_at": "",
    "handoff_status": "",
    "human_handoff": False,
    "active_lead_id": "LOCAL-EMAIL-TEST",
    "quote_data": {},
    "lead_data": {},
    "status": "AWAITING_EMAIL_CONFIRMATION",
    "last_message_id": "LOCAL_EMAIL_TEST_001",
}

lead = {
    "lead_id": "LOCAL-EMAIL-TEST",
}

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

session["quote_data"] = quote
session["lead_data"] = lead


# ------------------------------------------------------------------
# Test 1: Business owner quote email
# ------------------------------------------------------------------

print()
print("=" * 72)
print("TEST 1 - BUSINESS OWNER QUOTE EMAIL")
print("=" * 72)

owner_result = send_new_lead_email(
    session=session,
    quote=quote,
    lead=lead,
)

print("PASS - Business owner quote email sent.")
print("Message ID:", owner_result.get("id"))
print()
print("Check for heading: Calculations Involved")
print(
    "Expected final calculation: "
    "£1,200.00 + £200.00 + £0.00 = £1,400.00"
)


# ------------------------------------------------------------------
# Test 2: Customer quote email
# ------------------------------------------------------------------

print()
print("=" * 72)
print("TEST 2 - CUSTOMER QUOTE EMAIL")
print("=" * 72)

customer_quote_result = send_customer_quote_email(
    customer_email=customer_email,
    session=session,
    quote=quote,
    lead=lead,
)

print("PASS - Customer quote email sent.")
print("Message ID:", customer_quote_result.get("id"))


# ------------------------------------------------------------------
# Isolate main.py from Google Sheets for this email-only test
# ------------------------------------------------------------------

fake_sheets_service = types.ModuleType(
    "sheets_service"
)

fake_sheets_service.persist_completed_quote = (
    lambda *args, **kwargs: {
        "lead": lead,
        "conversation": {},
    }
)

fake_sheets_service.save_completed_lead = (
    lambda *args, **kwargs: lead
)

fake_sheets_service.update_lead = (
    lambda *args, **kwargs: lead
)

fake_sheets_service.get_pricing_rule = (
    lambda *args, **kwargs: {}
)

sys.modules[
    "sheets_service"
] = fake_sheets_service


fake_business_knowledge = types.ModuleType(
    "business_knowledge_service"
)

fake_business_knowledge.get_business_knowledge = (
    lambda *args, **kwargs: {
        "pricing": [],
        "packages": [],
        "business_info": [],
        "faqs": [],
    }
)

sys.modules[
    "business_knowledge_service"
] = fake_business_knowledge


# main.py can now import without contacting Google Sheets.
import main


# ------------------------------------------------------------------
# Test 3: main.py out-of-hours handoff
# ------------------------------------------------------------------

print()
print("=" * 72)
print("TEST 3 - MAIN.PY OUT-OF-HOURS HANDOFF")
print("=" * 72)

main.is_office_open = lambda: False


def fake_ensure_active_lead(
    session: dict,
):
    session["lead_data"] = lead
    session["active_lead_id"] = lead["lead_id"]
    return lead


def fake_update_active_lead(
    session: dict,
    updates: dict,
):
    session["lead_data"] = {
        **lead,
        **updates,
    }
    return session["lead_data"]


main.ensure_active_lead = (
    fake_ensure_active_lead
)

main.update_active_lead = (
    fake_update_active_lead
)


handoff_menu = main.process_handoff_request(
    session=session,
)

print()
print(
    "PASS - main.py processed forced out-of-hours handoff."
)

print()
print("Returned customer message:")
print(handoff_menu.get("message", ""))

print()
print(
    "Current stage:",
    session.get("current_stage"),
)

print(
    "Current status:",
    session.get("status"),
)

print(
    "Customer email retained:",
    session.get("customer_email"),
)


# ------------------------------------------------------------------
# Final expected emails
# ------------------------------------------------------------------

print()
print("=" * 72)
print("EMAIL + MAIN TEST COMPLETE")
print("=" * 72)

print("Expected real emails:")
print(
    "1. Business owner: Quote notification "
    "with Calculations Involved."
)
print(
    "2. Customer: Normal quote email."
)
print(
    "3. Business owner: Priority handoff notification."
)
print(
    "4. Customer: Out-of-hours acknowledgement email."
)
print()
print(
    "Google Sheets was intentionally bypassed in this test."
)
