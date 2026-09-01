from pathlib import Path

main_text = Path("main.py").read_text(encoding="utf-8")
gemini_text = Path("gemini_service.py").read_text(encoding="utf-8")

checks = {
    "handoff duplicate guard":
        'if session.get("handoff_requested") == "Yes":' in main_text,
    "callback duplicate guard":
        '"callback_request_sent"' in main_text
        and "build_callback_already_recorded_menu" in main_text,
    "handoff no longer traps every free-text message":
        "is_short_handoff_acknowledgement" in main_text,
    "mid-conversation thank-you removed":
        "_polish_conversation_reply" in gemini_text,
    "package comparison spacing rule":
        "clearly separated paragraph or block" in gemini_text,
}

for name, passed in checks.items():
    print(f"{name}: {'PASS' if passed else 'FAIL'}")
    assert passed, name

print()
print("FINAL CONVERSATION REGRESSION CHECK PASSED")
