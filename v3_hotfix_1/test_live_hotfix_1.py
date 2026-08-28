from __future__ import annotations

import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv


# ======================================================================
# Paths / environment
# ======================================================================

BASE_DIR = Path(__file__).resolve().parent

# Works from either:
#   project_root/
# or:
#   project_root/v3_foundation/
if (BASE_DIR / "business_knowledge_service.py").exists():
    PROJECT_ROOT = BASE_DIR
else:
    PROJECT_ROOT = BASE_DIR.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(1, str(PROJECT_ROOT))

load_dotenv(
    dotenv_path=PROJECT_ROOT / ".env",
    override=False,
)

from business_answer_service_v3 import BusinessAnswerServiceV3
from business_knowledge_adapter_v3 import BusinessKnowledgeAdapterV3
from business_question_coordinator_v3 import BusinessQuestionCoordinatorV3
from conversation_events import EventType
from conversation_models import ConversationContext, FlowState
from conversation_orchestrator import ConversationOrchestrator
from gemini_semantic_adapter import GeminiSemanticAdapter
from response_plan import ResponseAction
from semantic_contract import SemanticAction, SemanticInterpretation


# ======================================================================
# Helpers
# ======================================================================

def money_value(value) -> float:
    """Parse 950, 950.0, '£950', or '£1,200' into a float."""

    if value is None:
        return 0.0

    if isinstance(value, (int, float)):
        return float(value)

    cleaned = re.sub(
        r"[^0-9.\-]",
        "",
        str(value),
    )

    if cleaned in {"", "-", ".", "-."}:
        raise ValueError(
            f"Could not parse money value: {value!r}"
        )

    return float(cleaned)


def number_value(value) -> float:
    """Parse a simple numeric value such as 4, 4.0, or '4 hours'."""

    if value is None:
        return 0.0

    if isinstance(value, (int, float)):
        return float(value)

    match = re.search(
        r"-?\d+(?:\.\d+)?",
        str(value),
    )

    if not match:
        raise ValueError(
            f"Could not parse numeric value: {value!r}"
        )

    return float(match.group(0))


def normalized_text(text: str) -> str:
    """Ignore harmless currency/comma/spacing differences in assertions."""

    value = (
        str(text or "")
        .replace(",", "")
        .replace("£", "")
        .casefold()
    )

    return re.sub(
        r"\s+",
        " ",
        value,
    ).strip()


def require_in_answer(
    answer: str,
    required: str,
    description: str,
) -> None:
    if normalized_text(required) not in normalized_text(answer):
        raise AssertionError(
            f"Grounded answer is missing {description}: {required!r}"
        )


def require_money_in_answer(
    answer: str,
    value,
    description: str,
) -> None:
    amount = money_value(value)

    expected = (
        str(int(amount))
        if amount.is_integer()
        else f"{amount:g}"
    )

    require_in_answer(
        answer,
        expected,
        description,
    )


# ======================================================================
# Start
# ======================================================================

print()
print("=" * 72)
print("V3 PRODUCTION HOTFIX 1 - LIVE DEFECT REPRODUCTION TEST")
print("=" * 72)
print(
    "Uses real Gemini and real Google Sheets. "
    "Does not send Instagram messages or email."
)

if not os.getenv("GEMINI_API_KEY"):
    raise SystemExit(
        "GEMINI_API_KEY is not configured."
    )


# ======================================================================
# Live business catalogue
# ======================================================================

knowledge = BusinessKnowledgeAdapterV3(
    project_root=PROJECT_ROOT
)

catalogue = knowledge.get_catalogue()

if "Wedding" not in catalogue["supported_services"]:
    raise AssertionError(
        "Wedding service is not present in the live catalogue."
    )

packages = catalogue["packages_by_service"].get(
    "Wedding",
    [],
)

if not {"Basic", "Premium"}.issubset(set(packages)):
    raise AssertionError(
        "Wedding Basic/Premium packages are missing. "
        f"Got: {packages}"
    )

basic = knowledge.get_pricing(
    "Wedding",
    "Basic",
)

premium = knowledge.get_pricing(
    "Wedding",
    "Premium",
)

if not basic:
    raise AssertionError(
        "Live Wedding / Basic pricing row could not be loaded."
    )

if not premium:
    raise AssertionError(
        "Live Wedding / Premium pricing row could not be loaded."
    )

print()
print("LIVE SERVICES:", catalogue["supported_services"])
print("WEDDING PACKAGES:", packages)


# ======================================================================
# Real Gemini + V3 services
# ======================================================================

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
    quote_adapter=None,
)


# ======================================================================
# TEST 1
# Wedding is already known, package is not selected.
# Basic/Premium comparison must use Wedding's approved data.
# ======================================================================

context = ConversationContext(
    state=FlowState.QUOTE_PACKAGE
)
context.quote.service = "Wedding"

question_text = "What's the difference between basic and premium"

question_turn = orchestrator.handle_text(
    context=context,
    message_text=question_text,
)

print()
print("-" * 72)
print("TEST 1 - PRE-SELECTION PACKAGE COMPARISON")
print("-" * 72)
print("ACTION:", question_turn.interpretation.action.value)
print("STATE:", context.state.value)

if (
    question_turn.response_plan.action
    != ResponseAction.ANSWER_BUSINESS_QUESTION
):
    raise AssertionError(
        "Pre-selection Basic/Premium comparison did not become "
        "ANSWER_BUSINESS_QUESTION."
    )

if context.state != FlowState.BUSINESS_INTERRUPT:
    raise AssertionError(
        "Business question did not enter BUSINESS_INTERRUPT."
    )

resolution = coordinator.resolve(
    context=context,
    question_text=(
        question_turn.response_plan.business_question_text
        or question_text
    ),
    question_type=question_turn.response_plan.business_question_type,
    customer_language=question_turn.response_plan.language,
)

answer = resolution.answer.answer_text or ""

print()
print("ANSWER:")
print(answer)

require_in_answer(
    answer,
    "Wedding",
    "the already-known Wedding service",
)
require_in_answer(answer, "Basic", "Basic package")
require_in_answer(answer, "Premium", "Premium package")

for value, description in [
    (basic["photography_price"], "Basic photography price"),
    (basic["videography_price"], "Basic videography price"),
    (basic["both_price"], "Basic Both price"),
    (basic["extra_hour_rate"], "Basic extra-hour rate"),
    (premium["photography_price"], "Premium photography price"),
    (premium["videography_price"], "Premium videography price"),
    (premium["both_price"], "Premium Both price"),
    (premium["extra_hour_rate"], "Premium extra-hour rate"),
]:
    require_money_in_answer(
        answer,
        value,
        description,
    )

basic_hours = number_value(basic["included_hours"])
premium_hours = number_value(premium["included_hours"])

require_in_answer(
    answer,
    str(int(basic_hours) if basic_hours.is_integer() else basic_hours),
    "Basic included hours",
)
require_in_answer(
    answer,
    str(int(premium_hours) if premium_hours.is_integer() else premium_hours),
    "Premium included hours",
)

for forbidden_phrase in [
    "which service",
    "what service",
    "service are you interested",
    "which service are you interested",
]:
    if forbidden_phrase in normalized_text(answer):
        raise AssertionError(
            "The answer asked for a service that is already known "
            "to be Wedding."
        )

if context.state != FlowState.QUOTE_PACKAGE:
    raise AssertionError(
        "After answering the comparison the bot must resume "
        f"QUOTE_PACKAGE. Got: {context.state.value}"
    )

if context.quote.service != "Wedding":
    raise AssertionError(
        "Wedding service was unexpectedly changed."
    )

if context.quote.package is not None:
    raise AssertionError(
        "A package question must not silently select a package."
    )

print(
    "PASS 1 - comparison uses Wedding's approved Sheets data "
    "and resumes package selection"
)


# ======================================================================
# TEST 2
# Deterministic Python guarantee:
# package='Wedding' must be impossible even if an interpreter produced it.
# ======================================================================

print()
print("-" * 72)
print("TEST 2 - PYTHON CROSS-DOMAIN VALUE GUARD")
print("-" * 72)

synthetic_wrong = SemanticInterpretation(
    action=SemanticAction.FIELD_VALUE,
    field_name="package",
    value="Wedding",
    confidence=1.0,
    language="English",
)

guarded_interpretation, guarded_event = (
    orchestrator._guard_catalogue_value(
        context=context,
        interpretation=synthetic_wrong,
    )
)

if guarded_event is None:
    raise AssertionError(
        "Python catalogue guard failed to reject Wedding as a package."
    )

if guarded_event.type != EventType.INVALID_FIELD_VALUE:
    raise AssertionError(
        "Expected INVALID_FIELD_VALUE, got "
        f"{guarded_event.type.value}."
    )

if guarded_event.metadata.get("allowed_values") != [
    "Basic",
    "Premium",
]:
    raise AssertionError(
        "Python guard did not use the live Wedding package catalogue. "
        f"Got: {guarded_event.metadata.get('allowed_values')}"
    )

guard_transition = orchestrator.state_machine.handle(
    context,
    guarded_event,
)

guard_plan = orchestrator._plan_response(
    context=context,
    interpretation=guarded_interpretation,
    event=guarded_event,
    transition=guard_transition,
)

print("EVENT:", guarded_event.type.value)
print("STATE:", context.state.value)
print("PACKAGE:", context.quote.package)
print("OPTIONS:", guard_plan.options)

if context.state != FlowState.QUOTE_PACKAGE:
    raise AssertionError(
        "Cross-domain package value advanced the conversation."
    )

if context.quote.package is not None:
    raise AssertionError(
        "Cross-domain value corrupted package state."
    )

if guard_plan.options != ["Basic", "Premium"]:
    raise AssertionError(
        "Rejected package value did not re-offer Basic/Premium. "
        f"Got: {guard_plan.options}"
    )

print(
    "PASS 2 - Python independently blocks Wedding from becoming "
    "a package value"
)


# ======================================================================
# TEST 3
# Exact live customer input from screenshot.
# Regardless of Gemini classification, it cannot advance package state.
# ======================================================================

print()
print("-" * 72)
print("TEST 3 - LIVE WRONG-DOMAIN CUSTOMER INPUT")
print("-" * 72)

wrong_live = orchestrator.handle_text(
    context=context,
    message_text="Wedding",
)

print("ACTION:", wrong_live.interpretation.action.value)
print("EVENT:", wrong_live.event.type.value)
print("STATE:", context.state.value)
print("PACKAGE:", context.quote.package)

if context.state != FlowState.QUOTE_PACKAGE:
    raise AssertionError(
        "Typing Wedding while package was expected advanced the conversation."
    )

if context.quote.package is not None:
    raise AssertionError(
        "Typing Wedding corrupted package state: "
        f"{context.quote.package!r}"
    )

if wrong_live.response_plan.next_field != "package":
    raise AssertionError(
        "After wrong-domain input the bot did not remain focused on package."
    )

if wrong_live.response_plan.options != ["Basic", "Premium"]:
    raise AssertionError(
        "After wrong-domain input the bot did not re-offer Basic/Premium."
    )

print(
    "PASS 3 - live customer input Wedding cannot escape QUOTE_PACKAGE"
)


# ======================================================================
# TEST 4
# Valid package still works.
# ======================================================================

print()
print("-" * 72)
print("TEST 4 - VALID PACKAGE")
print("-" * 72)

valid = orchestrator.handle_text(
    context=context,
    message_text="Basic",
)

print("ACTION:", valid.interpretation.action.value)
print("STATE:", context.state.value)
print("PACKAGE:", context.quote.package)

if context.quote.package != "Basic":
    raise AssertionError(
        "Basic was not stored correctly. "
        f"Got: {context.quote.package!r}"
    )

if context.state != FlowState.QUOTE_COVERAGE:
    raise AssertionError(
        "Basic did not advance to QUOTE_COVERAGE. "
        f"Got: {context.state.value}"
    )

print(
    "PASS 4 - valid Basic selection still advances to coverage"
)


# ======================================================================
# TEST 5
# Basic is selected, coverage is expected, customer asks comparison again.
# Must preserve Basic and require explicit keep/switch decision.
# ======================================================================

print()
print("-" * 72)
print("TEST 5 - POST-SELECTION PACKAGE RECONSIDERATION")
print("-" * 72)

reconsideration_text = (
    "What's the difference between basic and premium"
)

reconsideration_turn = orchestrator.handle_text(
    context=context,
    message_text=reconsideration_text,
)

print("ACTION:", reconsideration_turn.interpretation.action.value)
print("STATE:", context.state.value)
print("PACKAGE:", context.quote.package)

if (
    reconsideration_turn.response_plan.action
    != ResponseAction.ANSWER_PACKAGE_RECONSIDERATION
):
    raise AssertionError(
        "Package comparison after Basic selection did not become "
        "ANSWER_PACKAGE_RECONSIDERATION."
    )

if context.state != FlowState.PACKAGE_RECONFIRMATION:
    raise AssertionError(
        "Package comparison after selection did not enter "
        "PACKAGE_RECONFIRMATION."
    )

if context.quote.package != "Basic":
    raise AssertionError(
        "Package reconsideration changed Basic before the customer "
        "made a keep/switch decision."
    )

reconsideration_resolution = (
    coordinator.resolve_package_reconsideration(
        context=context,
        question_text=(
            reconsideration_turn.response_plan.business_question_text
            or reconsideration_text
        ),
        question_type=(
            reconsideration_turn.response_plan.business_question_type
        ),
        customer_language=(
            reconsideration_turn.response_plan.language
        ),
    )
)

reconsideration_answer = (
    reconsideration_resolution.answer.answer_text
    or ""
)

print()
print("RECONSIDERATION ANSWER:")
print(reconsideration_answer)

require_in_answer(
    reconsideration_answer,
    "Wedding",
    "Wedding service",
)
require_in_answer(
    reconsideration_answer,
    "Basic",
    "Basic package",
)
require_in_answer(
    reconsideration_answer,
    "Premium",
    "Premium package",
)
require_money_in_answer(
    reconsideration_answer,
    basic["both_price"],
    "Basic Both price",
)
require_money_in_answer(
    reconsideration_answer,
    premium["both_price"],
    "Premium Both price",
)

if context.state != FlowState.PACKAGE_RECONFIRMATION:
    raise AssertionError(
        "Answering reconsideration unexpectedly left "
        "PACKAGE_RECONFIRMATION."
    )

if (
    reconsideration_resolution.resume_plan.action
    != ResponseAction.ASK_PACKAGE_RECONFIRMATION
):
    raise AssertionError(
        "Comparison answer was not followed by explicit package "
        "reconfirmation."
    )

if reconsideration_resolution.resume_plan.current_package != "Basic":
    raise AssertionError(
        "Reconfirmation did not preserve Basic as current package."
    )

if reconsideration_resolution.resume_plan.options != [
    "Basic",
    "Premium",
]:
    raise AssertionError(
        "Reconfirmation does not contain live Basic/Premium options."
    )

print(
    "PASS 5 - post-selection comparison preserves Basic and requires "
    "an explicit keep/switch decision"
)


# ======================================================================
# Final summary
# ======================================================================

print()
print("=" * 72)
print("V3 PRODUCTION HOTFIX 1 LIVE TEST PASSED")
print("=" * 72)
print("Verified:")
print("1. Wedding context is reused for Basic/Premium comparison.")
print("2. Approved Wedding pricing is used in the comparison.")
print("3. Cross-domain package values cannot mutate state.")
print("4. Valid Basic selection still progresses normally.")
print("5. Post-selection comparison enters explicit reconfirmation.")
