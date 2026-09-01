from sheets_service import save_lead


sender_id = "877021928624714"

lead = save_lead(
    sender_id=sender_id,
    quoted_price=660,
    status="QUOTE_READY",
    human_handoff=False,
    conversation_summary=(
        "Wedding photography enquiry in Birmingham "
        "for six hours on 14 September 2026."
    ),
)

if lead:
    print("Lead created successfully:")
    print(lead)
else:
    print("Conversation was not found.")