from button_action_service import process_button_action
from sheets_service import (
    create_conversation,
    get_conversation,
)


sender_id = "877021928624714"
recipient_id = "17841432120971202"
message_id = "TEST-MESSAGE-001"


conversation = get_conversation(sender_id)

if conversation is None:
    conversation = create_conversation(
        sender_id=sender_id,
        recipient_id=recipient_id,
        message_id=message_id,
    )

    print("Test conversation created.")


print()
print("Before:")
print(get_conversation(sender_id))


result = process_button_action(
    sender_id=sender_id,
    payload="GET_QUOTE",
)

print()
print("After GET_QUOTE:")
print(result)


result = process_button_action(
    sender_id=sender_id,
    payload="SERVICE_WEDDING",
)

print()
print("After SERVICE_WEDDING:")
print(result)


result = process_button_action(
    sender_id=sender_id,
    payload="PACKAGE_PREMIUM",
)

print()
print("After PACKAGE_PREMIUM:")
print(result)


result = process_button_action(
    sender_id=sender_id,
    payload="COVERAGE_BOTH",
)

print()
print("After COVERAGE_BOTH:")
print(result)


result = process_button_action(
    sender_id=sender_id,
    payload="TRAVEL_YES",
)

print()
print("After TRAVEL_YES:")
print(result)