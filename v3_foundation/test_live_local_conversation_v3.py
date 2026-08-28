from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent

load_dotenv(
    dotenv_path=PROJECT_ROOT / ".env",
    override=False,
)

project_root_text = str(PROJECT_ROOT)
if project_root_text not in sys.path:
    sys.path.insert(0, project_root_text)

from business_answer_service_v3 import BusinessAnswerServiceV3
from business_knowledge_adapter_v3 import BusinessKnowledgeAdapterV3
from business_question_coordinator_v3 import BusinessQuestionCoordinatorV3
from conversation_models import ConversationContext, FlowState
from conversation_orchestrator import ConversationOrchestrator
from customer_response_renderer_v3 import CustomerResponseRendererV3
from gemini_semantic_adapter import GeminiSemanticAdapter
from local_conversation_runtime_v3 import LocalConversationRuntimeV3
from quote_adapter_v3 import QuoteAdapterV3


def print_messages(result):
    for message in result.messages:
        print()
        print("BOT:")
        print(message.text)

        if message.buttons:
            print(
                "BUTTONS:",
                [
                    button.label
                    for button in message.buttons
                ],
            )


print()
print("=" * 72)
print("V3 BLOCK 7 - LIVE LOCAL END-TO-END CONVERSATION")
print("=" * 72)
print(
    "Uses real Gemini, real Google Sheets, and real quote_service."
)
print(
    "Does not send Instagram messages or email."
)

knowledge = BusinessKnowledgeAdapterV3(
    project_root=PROJECT_ROOT
)
catalogue = knowledge.get_catalogue()

semantic = GeminiSemanticAdapter()

orchestrator = ConversationOrchestrator(
    semantic_interpreter=semantic,
    supported_services=catalogue["supported_services"],
    packages_by_service=catalogue["packages_by_service"],
)

quote_adapter = QuoteAdapterV3(
    project_root=PROJECT_ROOT
)

answer_service = BusinessAnswerServiceV3(
    knowledge_adapter=knowledge
)

coordinator = BusinessQuestionCoordinatorV3(
    orchestrator=orchestrator,
    answer_service=answer_service,
    quote_adapter=quote_adapter,
)

runtime = LocalConversationRuntimeV3(
    orchestrator=orchestrator,
    business_coordinator=coordinator,
    quote_adapter=quote_adapter,
    renderer=CustomerResponseRendererV3(),
)

context = ConversationContext()

steps = [
    ("button", "GET_QUOTE"),
    ("text", "Wedding"),
    ("text", "Basic"),
    (
        "text",
        "wait tell me price difference one more time",
    ),
    ("text", "okay"),
    ("text", "premium kardo"),
    ("text", "both"),
    ("text", "no"),
    ("text", "8 hours"),
    ("text", "12 October"),
    ("text", "Birmingham"),
]

comparison_checked = False
package_pause_checked = False
package_switch_checked = False
final_quote = None

for step_type, value in steps:
    print()
    print("-" * 72)
    print(
        "INPUT:",
        value,
    )

    if step_type == "button":
        result = runtime.handle_button(
            context=context,
            payload=value,
        )
    else:
        result = runtime.handle_text(
            context=context,
            message_text=value,
        )

    print(
        "STATE:",
        context.state.value,
    )
    print(
        "QUOTE:",
        context.quote.as_dict(),
    )

    print_messages(result)

    if value == "wait tell me price difference one more time":
        if context.state != FlowState.PACKAGE_RECONFIRMATION:
            raise AssertionError(
                "Package comparison did not enter reconfirmation."
            )

        if len(result.messages) < 2:
            raise AssertionError(
                "Package comparison did not return answer + reconfirmation."
            )

        answer_text = result.messages[0].text
        reconfirm_text = result.messages[1].text

        if "Basic selected" not in reconfirm_text:
            raise AssertionError(
                "Reconfirmation did not preserve Basic selection."
            )

        if (
            "continue with Basic"
            not in reconfirm_text
        ):
            raise AssertionError(
                "Reconfirmation did not ask to keep Basic."
            )

        comparison_checked = True

    if value == "okay":
        if context.state != FlowState.PACKAGE_RECONFIRMATION:
            raise AssertionError(
                "Bare okay incorrectly left package reconfirmation."
            )

        package_pause_checked = True

    if value == "premium kardo":
        if context.quote.package != "Premium":
            raise AssertionError(
                "Package was not switched to Premium."
            )

        if context.state != FlowState.QUOTE_COVERAGE:
            raise AssertionError(
                "Package switch did not resume coverage."
            )

        package_switch_checked = True

    if result.quote:
        final_quote = result.quote


if not comparison_checked:
    raise AssertionError(
        "Package comparison behavior was not checked."
    )

if not package_pause_checked:
    raise AssertionError(
        "Package pause behavior was not checked."
    )

if not package_switch_checked:
    raise AssertionError(
        "Package switch behavior was not checked."
    )

if context.state != FlowState.QUOTE_READY:
    raise AssertionError(
        f"Expected QUOTE_READY, got {context.state.value}."
    )

if not final_quote:
    raise AssertionError(
        "Final deterministic quote was not produced."
    )

if float(final_quote["quote_total"]) != 1400.0:
    raise AssertionError(
        f"Expected £1400 quote, got "
        f"£{final_quote['quote_total']}."
    )

for step_type, value in steps:
    pass

print()
print("=" * 72)
print("LIVE LOCAL CONVERSATION SUMMARY")
print("=" * 72)
print(
    "Package comparison answered first: PASS"
)
print(
    "Keep Basic / switch prompt shown: PASS"
)
print(
    "Bare okay stayed in reconfirmation: PASS"
)
print(
    "Premium switch resumed coverage: PASS"
)
print(
    "Real deterministic final quote: £1400"
)
print()
print(
    "V3 BLOCK 7 LIVE LOCAL END-TO-END CONVERSATION PASSED"
)
