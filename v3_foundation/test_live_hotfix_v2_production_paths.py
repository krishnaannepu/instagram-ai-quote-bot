from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent

load_dotenv(
    dotenv_path=PROJECT_ROOT / ".env",
    override=False,
)

root_text = str(PROJECT_ROOT)

if root_text not in sys.path:
    sys.path.insert(
        0,
        root_text,
    )

from business_answer_service_v3 import BusinessAnswerServiceV3
from business_knowledge_adapter_v3 import BusinessKnowledgeAdapterV3
from business_question_coordinator_v3 import BusinessQuestionCoordinatorV3
from conversation_models import ConversationContext, FlowState
from conversation_orchestrator import ConversationOrchestrator
from gemini_semantic_adapter import GeminiSemanticAdapter


print()
print("=" * 72)
print("V3 PRODUCTION HOTFIX V2 - LIVE PRODUCTION PATH TEST")
print("=" * 72)
print(
    "Uses real Gemini semantics and real Google Sheets knowledge. "
    "Does not call Instagram, Gmail, or Cloud Run."
)

knowledge = BusinessKnowledgeAdapterV3(
    project_root=PROJECT_ROOT
)

catalogue = knowledge.get_catalogue()

semantic = GeminiSemanticAdapter()

orchestrator = ConversationOrchestrator(
    semantic_interpreter=semantic,
    supported_services=catalogue[
        "supported_services"
    ],
    packages_by_service=catalogue[
        "packages_by_service"
    ],
)

answer_service = BusinessAnswerServiceV3(
    knowledge_adapter=knowledge
)

coordinator = BusinessQuestionCoordinatorV3(
    orchestrator=orchestrator,
    answer_service=answer_service,
    quote_adapter=None,
)


# ------------------------------------------------------------------
# Exact production defect 1
# ------------------------------------------------------------------

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
print("PYTHON EVENT:", result.event.type.value)
print("STATE AFTER:", context.state.value)
print("PACKAGE AFTER:", context.quote.package)

if context.state != FlowState.QUOTE_PACKAGE:
    raise AssertionError(
        "Wedding incorrectly advanced the package state."
    )

if context.quote.package is not None:
    raise AssertionError(
        "Wedding was incorrectly stored as a package."
    )

if result.event.type.value != "INVALID_FIELD_VALUE":
    raise AssertionError(
        "Wrong-domain Wedding value was not rejected by Python."
    )

print(
    "PASS 1 - Wedding stays rejected while package remains required"
)


# ------------------------------------------------------------------
# Exact production defect 2
# ------------------------------------------------------------------

comparison = orchestrator.handle_text(
    context=context,
    message_text=(
        "What's the difference between basic and premium"
    ),
)

print()
print("PACKAGE COMPARISON")
print(
    "SEMANTIC ACTION:",
    comparison.interpretation.action.value
    if comparison.interpretation
    else "NONE",
)
print(
    "QUESTION TYPE:",
    comparison.response_plan.business_question_type,
)

if context.state != FlowState.BUSINESS_INTERRUPT:
    raise AssertionError(
        "Package comparison did not enter business-question interrupt."
    )

resolution = coordinator.resolve(
    context=context,
    question_text=(
        comparison.response_plan
        .business_question_text
        or ""
    ),
    question_type=(
        comparison.response_plan
        .business_question_type
    ),
    customer_language=(
        comparison.response_plan.language
        or "English"
    ),
)

answer = (
    resolution.answer.answer_text
    or ""
)

print()
print("ANSWER:")
print(answer)

if context.state != FlowState.QUOTE_PACKAGE:
    raise AssertionError(
        "Package comparison did not resume package selection."
    )

if "which service" in answer.casefold():
    raise AssertionError(
        "Answer incorrectly asked for the service again."
    )

if "Wedding" not in answer:
    raise AssertionError(
        "Answer did not use the already-selected Wedding service."
    )

basic = knowledge.get_pricing(
    "Wedding",
    "Basic",
)

premium = knowledge.get_pricing(
    "Wedding",
    "Premium",
)

if not basic or not premium:
    raise AssertionError(
        "Wedding Basic/Premium pricing rows are missing."
    )


def money(value):
    number = float(
        str(
            value
        )
        .replace(
            "£",
            "",
        )
        .replace(
            ",",
            "",
        )
    )

    if number.is_integer():
        return f"£{number:,.0f}"

    return f"£{number:,.2f}"


expected_values = [
    money(
        basic[
            "photography_price"
        ]
    ),
    money(
        basic[
            "videography_price"
        ]
    ),
    money(
        basic[
            "both_price"
        ]
    ),
    money(
        premium[
            "photography_price"
        ]
    ),
    money(
        premium[
            "videography_price"
        ]
    ),
    money(
        premium[
            "both_price"
        ]
    ),
]

for expected in expected_values:
    if expected not in answer:
        raise AssertionError(
            f"Approved Wedding price missing from answer: {expected}"
        )

print(
    "PASS 2 - package comparison uses exact Wedding pricing"
)
print(
    "PASS 3 - answer cannot ask for the service again"
)
print(
    "PASS 4 - flow resumes QUOTE_PACKAGE after answering"
)

print()
print("=" * 72)
print("V3 PRODUCTION HOTFIX V2 LIVE TEST PASSED")
print("=" * 72)
