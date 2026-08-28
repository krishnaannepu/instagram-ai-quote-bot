from qualification_service import evaluate_conversation


sender_id = "877021928624714"

result = evaluate_conversation(sender_id)

print("Qualified:")
print(result["qualified"])

print("\nMissing fields:")
print(result["missing_fields"])

print("\nNext field:")
print(result["next_field"])

print("\nNext question:")
print(result["next_question"])

print("\nUpdated conversation:")
print(result["conversation"])