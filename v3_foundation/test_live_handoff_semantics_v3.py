from __future__ import annotations

import os
import sys
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

if not os.getenv("GEMINI_API_KEY"):
    print("GEMINI_API_KEY is not configured.")
    sys.exit(1)


adapter = GeminiSemanticAdapter()


def run_case(
    label,
    context,
    message,
    expected_action,
    expected_value=None,
):
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
        packages_for_service=[
            "Basic",
            "Premium",
        ],
    )

    print()
    print(label)
    print("STATE:", context.state.value)
    print("MESSAGE:", message)
    print("ACTION:", result.action.value)
    print("VALUE:", result.value)

    if result.action != expected_action:
        raise AssertionError(
            f"Expected {expected_action.value}, "
            f"got {result.action.value}."
        )

    if (
        expected_value is not None
        and result.value != expected_value
    ):
        raise AssertionError(
            f"Expected value {expected_value!r}, "
            f"got {result.value!r}."
        )

    print("RESULT: PASS")


context = ConversationContext(
    state=FlowState.POST_QUOTE
)
context.quote.service = "Wedding"
context.quote.package = "Premium"

run_case(
    "CASE 1 - natural human handoff",
    context,
    "I want to speak to your team",
    SemanticAction.SPEAK_TO_TEAM,
)

context = ConversationContext(
    state=FlowState.QUOTE_COVERAGE
)
context.quote.service = "Wedding"
context.quote.package = "Basic"

run_case(
    "CASE 2 - Hinglish callback request during quote",
    context,
    "mujhe call karo",
    SemanticAction.REQUEST_CALLBACK,
)

context = ConversationContext(
    state=FlowState.CALLBACK_PREFERENCE
)

run_case(
    "CASE 3 - Hindi morning callback preference",
    context,
    "subah call karna",
    SemanticAction.CALLBACK_PREFERENCE_VALUE,
    "Morning",
)

context = ConversationContext(
    state=FlowState.CALLBACK_PREFERENCE
)

run_case(
    "CASE 4 - ASAP preference",
    context,
    "as soon as possible please",
    SemanticAction.CALLBACK_PREFERENCE_VALUE,
    "ASAP",
)

context = ConversationContext(
    state=FlowState.CALLBACK_RECORDED
)
context.lifecycle.callback_request_sent = True

run_case(
    "CASE 5 - duplicate callback meaning remains explicit",
    context,
    "can you call me again?",
    SemanticAction.REQUEST_CALLBACK,
)

print()
print("=" * 72)
print("V3 BLOCK 10 LIVE HANDOFF SEMANTIC TEST PASSED")
print("=" * 72)
