from pathlib import Path

main = Path("main.py").read_text(encoding="utf-8")
gem = Path("gemini_service.py").read_text(encoding="utf-8")
ai = Path("ai_conversation_service.py").read_text(encoding="utf-8")

checks = [
    (
        "contact phone question type exists",
        "CONTACT_PHONE_NUMBER" in gem,
    ),
    (
        "phone question separated from speak-to-team",
        "Do NOT use SPEAK_TO_TEAM when the customer only asks for our phone number"
        in gem,
    ),
    (
        "phone question separated from callback",
        "Do NOT use REQUEST_CALLBACK when the customer only asks to see our phone"
        in gem,
    ),
    (
        "AI routes phone question deterministically",
        '"SHOW_BUSINESS_PHONE"' in ai,
    ),
    (
        "main displays configured business number",
        "def build_business_phone_message()" in main
        and "BUSINESS_PHONE_NUMBER" in main,
    ),
    (
        "main handles phone action",
        'if action == "SHOW_BUSINESS_PHONE":' in main,
    ),
]

for name, passed in checks:
    print(f"{name}: {'PASS' if passed else 'FAIL'}")
    assert passed, name

print()
print("CONTACT NUMBER ROUTING TEST PASSED")
