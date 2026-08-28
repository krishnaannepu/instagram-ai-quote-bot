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


if not os.getenv("GEMINI_API_KEY"):
    raise SystemExit("GEMINI_API_KEY is not configured.")

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
answer_service = BusinessAnswerServiceV3(
    knowledge_adapter=knowledge
)
coordinator = BusinessQuestionCoordinatorV3(
    orchestrator=orchestrator,
    answer_service=answer_service,
)
renderer = CustomerResponseRendererV3()

print()
print("=" * 72)
print("V3 PRODUCTION HOTFIX - LIVE GEMINI + REAL SHEETS")
print("=" * 72)
print("No Instagram message or email is sent by this test.")

# ------------------------------------------------------------------
# Production defect 1: service already known, ask package difference.
# ------------------------------------------------------------------
context = ConversationContext(
    state=FlowState.QUOTE_PACKAGE
)
context.quote.service = "Wedding"

turn = orchestrator.handle_text(
    context=context,
    message_text="What's the difference between basic and premium?",
)

if turn.response_plan.action.value != "ANSWER_BUSINESS_QUESTION":
    raise AssertionError(
        "Expected package question to be treated as BUSINESS_QUESTION before "
        "a package is selected. Got: "
        + turn.response_plan.action.value
    )

resolution = coordinator.resolve(
    context=context,
    question_text=turn.response_plan.business_question_text or "",
    question_type=turn.response_plan.business_question_type,
    customer_language=turn.response_plan.language,
)

messages = renderer.render_business_answer(
    answer=resolution.answer,
    follow_up=resolution.resume_plan,
)

print()
print("CASE 1 ANSWER:")
print(messages[0].text)
print()
print("CASE 1 FOLLOW-UP:")
print(messages[1].text)

if context.state != FlowState.QUOTE_PACKAGE:
    raise AssertionError(
        f"Expected QUOTE_PACKAGE after comparison; got {context.state.value}."
    )

if context.quote.service != "Wedding":
    raise AssertionError("Wedding service context was lost.")

if "£500" not in messages[0].text or "£1200" not in messages[0].text:
    raise AssertionError(
        "Exact Wedding Basic/Premium pricing was not included."
    )

if "which service" in messages[0].text.lower():
    raise AssertionError(
        "Bot asked for the service even though Wedding was already known."
    )

print("PASS 1 - known Wedding service produces exact package comparison")

# ------------------------------------------------------------------
# Production defect 2: service-specific package comparison from IDLE.
# ------------------------------------------------------------------
context2 = ConversationContext(
    state=FlowState.IDLE
)

turn = orchestrator.handle_text(
    context=context2,
    message_text=(
        "give me the difference between them for wedding specific "
        "along with prices"
    ),
)

if turn.response_plan.action.value != "ANSWER_BUSINESS_QUESTION":
    raise AssertionError(
        "Expected service-specific package enquiry to be a business question; "
        f"got {turn.response_plan.action.value}."
    )

resolution = coordinator.resolve(
    context=context2,
    question_text=turn.response_plan.business_question_text or "",
    question_type=turn.response_plan.business_question_type,
    customer_language=turn.response_plan.language,
)

messages = renderer.render_business_answer(
    answer=resolution.answer,
    follow_up=resolution.resume_plan,
)

print()
print("CASE 2 ANSWER:")
print(messages[0].text)
print()
print("CASE 2 FOLLOW-UP:")
print(messages[1].text)

if context2.quote.service != "Wedding":
    raise AssertionError("Wedding was not preserved from the customer enquiry.")

if context2.state != FlowState.QUOTE_PACKAGE:
    raise AssertionError(
        f"Expected QUOTE_PACKAGE; got {context2.state.value}."
    )

if "Basic or Premium" not in messages[1].text:
    raise AssertionError("The customer was not asked for the package choice.")

if messages[1].text.startswith("Hi!"):
    raise AssertionError("Conversation incorrectly reset to the welcome greeting.")

print("PASS 2 - IDLE Wedding comparison becomes a continuing Wedding quote")

# Acknowledgement must not throw away the package decision state.
ack = orchestrator.handle_text(
    context=context2,
    message_text="got it",
)

if context2.state != FlowState.QUOTE_PACKAGE:
    raise AssertionError(
        f"'got it' changed state to {context2.state.value}."
    )

print("PASS 3 - acknowledgement preserves the pending package choice")

basic = orchestrator.handle_text(
    context=context2,
    message_text="okay do basic",
)

if context2.quote.package != "Basic":
    raise AssertionError(
        f"Expected Basic; got {context2.quote.package!r}."
    )

if context2.state != FlowState.QUOTE_COVERAGE:
    raise AssertionError(
        f"Expected QUOTE_COVERAGE; got {context2.state.value}."
    )

print("PASS 4 - natural Basic selection continues to coverage")

print()
print("=" * 72)
print("V3 PRODUCTION HOTFIX LIVE TEST PASSED")
print("=" * 72)
