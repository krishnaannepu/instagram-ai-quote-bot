from sheets_service import close_conversation


sender_id = "877021928624714"

result = close_conversation(
    sender_id=sender_id,
    conversation_summary="Completed customer enquiry.",
)

print("Lifecycle result:")
print(result)