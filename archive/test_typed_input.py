from sheets_service import get_conversation
from typed_input_service import process_typed_input


sender_id = "877021928624714"


print("Before:")
print(get_conversation(sender_id))


result = process_typed_input(
    sender_id=sender_id,
    message_text="6",
)

print()
print("After duration:")
print(result)


result = process_typed_input(
    sender_id=sender_id,
    message_text="20 September 2026",
)

print()
print("After event date:")
print(result)


result = process_typed_input(
    sender_id=sender_id,
    message_text="Birmingham",
)

print()
print("After location:")
print(result)