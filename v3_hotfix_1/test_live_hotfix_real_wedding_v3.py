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

project_root_text = str(PROJECT_ROOT)
if project_root_text not in sys.path:
    sys.path.insert(
        0,
        project_root_text,
    )

from business_answer_service_v3 import BusinessAnswerServiceV3
from business_knowledge_adapter_v3 import BusinessKnowledgeAdapterV3
from conversation_models import ConversationContext, FlowState
from conversation_orchestrator import ConversationOrchestrator
from semantic_contract import SemanticAction, SemanticInterpretation


class OneMeaningInterpreter:
    def __init__(self, interpretation):
        self.interpretation = interpretation

    def interpret(self, context, message_text, **kwargs):
        return self.interpretation


print()
print("=" * 72)
print("V3 HOTFIX 1 - REAL WEDDING GROUNDING CHECK")
print("=" * 72)
print(
    "Uses real Google Sheets. Does not send Instagram messages or email."
)

knowledge = BusinessKnowledgeAdapterV3(
    project_root=PROJECT_ROOT
)

all_knowledge = knowledge.get_all(
    force_refresh=True
)

catalogue = knowledge.get_catalogue()

assert "Wedding" in catalogue["supported_services"]
assert set(
    catalogue["packages_by_service"]["Wedding"]
) >= {
    "Basic",
    "Premium",
}

context = ConversationContext(
    state=FlowState.QUOTE_PACKAGE
)
context.quote.service = "Wedding"

# Core package comparison is deterministic and therefore needs no Gemini call.
answer_service = BusinessAnswerServiceV3(
    knowledge_adapter=knowledge,
    client=object(),
)

answer = answer_service.answer(
    context=context,
    question_text=(
        "What's the difference between basic and premium"
    ),
    question_type=None,
    customer_language="English",
)

print()
print("ANSWER:")
print(answer.answer_text)

assert answer.answer_found is True
assert answer.answer_text
assert "For Wedding" in answer.answer_text
assert "Basic:" in answer.answer_text
assert "Premium:" in answer.answer_text
assert "which service" not in answer.answer_text.lower()
assert "service you have in mind" not in answer.answer_text.lower()

# Ensure numbers in the answer actually come from current Wedding Pricing rows.
wedding_rows = [
    row
    for row in all_knowledge["pricing"]
    if str(row.get("service", "")).strip().casefold()
    == "wedding"
]

by_package = {
    str(row.get("package", "")).strip().casefold(): row
    for row in wedding_rows
}

for package_name in ("basic", "premium"):
    row = by_package[package_name]
    for key in (
        "included_hours",
        "photography_price",
        "videography_price",
        "both_price",
        "extra_hour_rate",
    ):
        raw = str(row[key]).replace("£", "").replace(",", "")
        number = float(raw)
        expected = (
            f"{int(number):,}"
            if number.is_integer()
            else f"{number:,.2f}"
        )
        assert expected in answer.answer_text

print()
print("PASS 1 - real Wedding package comparison is exact and service-grounded")

# Reproduce the production defect directly: even if the semantic layer returns
# FIELD_VALUE(package='Wedding'), Python must refuse it.
interpreter = OneMeaningInterpreter(
    SemanticInterpretation(
        action=SemanticAction.FIELD_VALUE,
        field_name="package",
        value="Wedding",
        confidence=0.99,
        language="English",
    )
)

orchestrator = ConversationOrchestrator(
    semantic_interpreter=interpreter,
    supported_services=catalogue["supported_services"],
    packages_by_service=catalogue["packages_by_service"],
)

context2 = ConversationContext(
    state=FlowState.QUOTE_PACKAGE
)
context2.quote.service = "Wedding"

turn = orchestrator.handle_text(
    context=context2,
    message_text="Wedding",
)

assert context2.state == FlowState.QUOTE_PACKAGE
assert context2.quote.package is None
assert turn.event.type.value == "INVALID_FIELD_VALUE"
assert turn.response_plan.options == [
    "Basic",
    "Premium",
]

print("PASS 2 - invalid Wedding-as-package is blocked by Python")

print()
print("=" * 72)
print("V3 HOTFIX 1 REAL WEDDING CHECK PASSED")
print("=" * 72)
