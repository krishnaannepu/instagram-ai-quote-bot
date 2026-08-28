from conversation_service import process_customer_message


sender_id = "877021928624714"

message = "The wedding is on 14 September 2026."

result = process_customer_message(
    sender_id=sender_id,
    message_text=message,
)

print("Customer message:")
print(message)

print("\nExtracted fields:")
print(result["extracted_fields"])

print("\nUpdated conversation:")
print(result["conversation"])