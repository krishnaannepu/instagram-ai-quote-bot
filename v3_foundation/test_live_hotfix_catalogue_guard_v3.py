from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

from conversation_models import ConversationContext, FlowState
from conversation_orchestrator import ConversationOrchestrator
from gemini_semantic_adapter import GeminiSemanticAdapter


BASE_DIR = Path(__file__).resolve().parent

for dotenv_path in [
    BASE_DIR / ".env",
    BASE_DIR.parent / ".env",
    BASE_DIR.parent.parent / ".env",
]:
    if dotenv_path.exists():
        load_dotenv(
            dotenv_path=dotenv_path,
            override=False,
        )
        break

if not os.getenv("GEMINI_API_KEY"):
    raise SystemExit("GEMINI_API_KEY is not configured.")

orchestrator = ConversationOrchestrator(
    semantic_interpreter=GeminiSemanticAdapter(),
    supported_services=[
        "Wedding",
        "Birthday",
        "Portrait",
        "Event",
    ],
    packages_by_service={
        "Wedding": ["Basic", "Premium"],
        "Birthday": ["Basic", "Premium"],
        "Portrait": ["Basic", "Premium"],
        "Event": ["Basic", "Premium"],
    },
)

# Exact production failure from Instagram.
context = ConversationContext(
    state=FlowState.QUOTE_PACKAGE
)
context.quote.service = "Wedding"

result = orchestrator.handle_text(
    context=context,
    message_text="Wedding",
)

print()
print("INVALID PACKAGE CASE")
print("GEMINI ACTION:", result.interpretation.action.value)
print("GEMINI VALUE:", result.interpretation.value)
print("PYTHON EVENT:", result.event.type.value)
print("STATE AFTER:", context.state.value)
print("PACKAGE AFTER:", context.quote.package)

if context.state != FlowState.QUOTE_PACKAGE:
    raise AssertionError(
        "Wedding incorrectly advanced the package state."
    )

if context.quote.package is not None:
    raise AssertionError(
        "Wedding incorrectly became a package value."
    )

if result.response_plan.next_field != "package":
    raise AssertionError(
        "Bot did not remain focused on package selection."
    )

print("RESULT: PASS - Wedding cannot advance package selection")

# Normal package selection must still work.
context2 = ConversationContext(
    state=FlowState.QUOTE_PACKAGE
)
context2.quote.service = "Wedding"

result2 = orchestrator.handle_text(
    context=context2,
    message_text="Premium",
)

print()
print("VALID PACKAGE CASE")
print("GEMINI ACTION:", result2.interpretation.action.value)
print("GEMINI VALUE:", result2.interpretation.value)
print("PYTHON EVENT:", result2.event.type.value)
print("STATE AFTER:", context2.state.value)
print("PACKAGE AFTER:", context2.quote.package)

if context2.quote.package != "Premium":
    raise AssertionError(
        "Valid Premium package was not accepted."
    )

if context2.state != FlowState.QUOTE_COVERAGE:
    raise AssertionError(
        "Valid Premium package did not advance to coverage."
    )

print("RESULT: PASS - valid package still advances normally")

print()
print("=" * 72)
print("V3 LIVE CATALOGUE GUARD HOTFIX TEST PASSED")
print("=" * 72)
