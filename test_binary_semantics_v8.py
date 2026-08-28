from pathlib import Path

gem = Path("gemini_service.py").read_text(encoding="utf-8")
ai = Path("ai_conversation_service.py").read_text(encoding="utf-8")

checks = [
    (
        "travel action phrase means yes",
        '"okay kardo", "kar do", "kardo", "go ahead", "do it"' in gem,
    ),
    (
        "bare okay can pause",
        '"okay", "got it", "hmm okay" -> PAUSE' in gem,
    ),
    (
        "pause cannot override clear binary approval",
        "do NOT use PAUSE when the phrase contains clear action/permission"
        in gem,
    ),
    (
        "travel remains canonical yes/no",
        '"Yes",\\n                "No"' in ai
        or '"Yes",\n                "No"' in ai,
    ),
    (
        "no Python hardcoded okay-kardo travel branch",
        "okay kardo" not in ai.lower(),
    ),
]

for name, passed in checks:
    print(f"{name}: {'PASS' if passed else 'FAIL'}")
    assert passed, name

print()
print("BINARY SEMANTICS REGRESSION TEST PASSED")
print("okay kardo / kar do / go ahead -> Yes for travel")
print("bare okay -> can remain a pause")
