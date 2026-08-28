from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

from conversation_models import ConversationContext, FlowState
from gemini_semantic_adapter import GeminiSemanticAdapter
from semantic_contract import SemanticAction


BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent

load_dotenv(
    dotenv_path=PROJECT_ROOT / ".env",
    override=False,
)

if not os.getenv(
    "GEMINI_API_KEY"
):
    raise SystemExit(
        "GEMINI_API_KEY is not configured."
    )


adapter = GeminiSemanticAdapter()

cases = [
    ("Hi", SemanticAction.GREETING),
    ("Yo", SemanticAction.GREETING),
    ("namaste", SemanticAction.GREETING),
    (
        "I want to speak to your team",
        SemanticAction.SPEAK_TO_TEAM,
    ),
    (
        "mujhe call karo",
        SemanticAction.REQUEST_CALLBACK,
    ),
]


for index, (
    message,
    expected,
) in enumerate(
    cases,
    start=1,
):
    context = ConversationContext(
        state=FlowState.IDLE
    )

    result = adapter.interpret(
        context=context,
        message_text=message,
        allowed_values=[],
        supported_services=[
            "Wedding",
            "Birthday",
            "Portrait",
            "Event",
        ],
        packages_for_service=[],
    )

    print()
    print(
        f"CASE {index}: {message!r}"
    )
    print(
        "ACTION:",
        result.action.value,
    )

    if result.action != expected:
        raise AssertionError(
            f"Expected {expected.value}, "
            f"got {result.action.value}."
        )

    print(
        "RESULT: PASS"
    )


print()
print("=" * 72)
print("V3 BLOCK 11 LIVE ENTRY SEMANTIC TEST PASSED")
print("=" * 72)
