from __future__ import annotations

import os
import sys
import time
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    print(
        "python-dotenv is not installed. "
        "Install project requirements first."
    )
    sys.exit(1)

from conversation_models import (
    ConversationContext,
    FlowState,
)
from gemini_semantic_adapter import (
    GeminiSemanticAdapter,
    GeminiSemanticAdapterError,
)
from semantic_contract import SemanticAction


# ------------------------------------------------------------------
# Environment
# ------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent

load_dotenv(
    dotenv_path=PROJECT_ROOT / ".env",
    override=False,
)

load_dotenv(
    dotenv_path=BASE_DIR / ".env",
    override=False,
)

if not os.getenv("GEMINI_API_KEY"):
    print()
    print("=" * 72)
    print("GEMINI_API_KEY NOT FOUND")
    print("=" * 72)
    print(
        "Expected it in the project .env file at:"
    )
    print(PROJECT_ROOT / ".env")
    print()
    print(
        "Do not paste the API key into this script."
    )
    sys.exit(1)


adapter = GeminiSemanticAdapter()


# ------------------------------------------------------------------
# Test helpers
# ------------------------------------------------------------------

def make_context(
    state: FlowState,
    *,
    service: str | None = None,
    package: str | None = None,
    coverage_type: str | None = None,
    travel_required: str | None = None,
    duration_hours=None,
    event_date: str | None = None,
    location: str | None = None,
    deferred_fields=None,
):
    context = ConversationContext(
        state=state
    )

    context.quote.service = service
    context.quote.package = package
    context.quote.coverage_type = coverage_type
    context.quote.travel_required = travel_required
    context.quote.duration_hours = duration_hours
    context.quote.event_date = event_date
    context.quote.location = location

    context.deferred_fields = list(
        deferred_fields or []
    )

    return context


def expected_values_for_state(
    state: FlowState,
):
    if state == FlowState.QUOTE_SERVICE:
        return [
            "Wedding",
            "Birthday",
            "Portrait",
            "Event",
        ]

    if state == FlowState.QUOTE_PACKAGE:
        return [
            "Basic",
            "Premium",
        ]

    if state == FlowState.QUOTE_COVERAGE:
        return [
            "Photography",
            "Videography",
            "Both",
        ]

    if state == FlowState.QUOTE_TRAVEL:
        return [
            "Yes",
            "No",
        ]

    return []


def run_case(
    number: int,
    *,
    label: str,
    context: ConversationContext,
    message: str,
    expected_actions: set[SemanticAction],
    expected_field: str | None = None,
    expected_value=None,
    forbidden_value=None,
):
    print()
    print("-" * 72)
    print(
        f"CASE {number}: {label}"
    )
    print("-" * 72)

    print(
        "STATE:",
        context.state.value,
    )
    print(
        "MESSAGE:",
        repr(message),
    )

    try:
        result = adapter.interpret(
            context=context,
            message_text=message,
            allowed_values=(
                expected_values_for_state(
                    context.state
                )
            ),
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

    except GeminiSemanticAdapterError as error:
        print(
            "RESULT: FAIL - adapter error"
        )
        print(error)
        return False

    print(
        "ACTION:",
        result.action.value,
    )
    print(
        "FIELD:",
        result.field_name,
    )
    print(
        "VALUE:",
        result.value,
    )
    print(
        "LANGUAGE:",
        result.language,
    )
    print(
        "CONFIDENCE:",
        result.confidence,
    )

    failures = []

    if result.action not in expected_actions:
        failures.append(
            "unexpected action "
            f"{result.action.value}; expected one of "
            f"{sorted(a.value for a in expected_actions)}"
        )

    if (
        expected_field is not None
        and result.field_name != expected_field
    ):
        failures.append(
            f"expected field {expected_field!r}, "
            f"got {result.field_name!r}"
        )

    if (
        expected_value is not None
        and result.value != expected_value
    ):
        failures.append(
            f"expected value {expected_value!r}, "
            f"got {result.value!r}"
        )

    if (
        forbidden_value is not None
        and result.value == forbidden_value
    ):
        failures.append(
            f"forbidden value {forbidden_value!r} was returned"
        )

    if failures:
        print(
            "RESULT: FAIL"
        )

        for failure in failures:
            print(
                " -",
                failure,
            )

        return False

    print(
        "RESULT: PASS"
    )

    return True


# ------------------------------------------------------------------
# Live cases
# ------------------------------------------------------------------

cases = [
    {
        "label":
            "service selection",
        "context":
            make_context(
                FlowState.QUOTE_SERVICE
            ),
        "message":
            "Wedding",
        "expected_actions": {
            SemanticAction.FIELD_VALUE,
        },
        "expected_field":
            "service",
        "expected_value":
            "Wedding",
    },
    {
        "label":
            "Hinglish package selection",
        "context":
            make_context(
                FlowState.QUOTE_PACKAGE,
                service="Wedding",
            ),
        "message":
            "basic kardo",
        "expected_actions": {
            SemanticAction.FIELD_VALUE,
        },
        "expected_field":
            "package",
        "expected_value":
            "Basic",
    },
    {
        "label":
            "package question before package selection",
        "context":
            make_context(
                FlowState.QUOTE_PACKAGE,
                service="Wedding",
            ),
        "message":
            "premium kya hota hai?",
        "expected_actions": {
            SemanticAction.BUSINESS_QUESTION,
        },
    },
    {
        "label":
            "bare both while coverage is authoritative",
        "context":
            make_context(
                FlowState.QUOTE_COVERAGE,
                service="Wedding",
                package="Basic",
            ),
        "message":
            "both",
        "expected_actions": {
            SemanticAction.FIELD_VALUE,
        },
        "expected_field":
            "coverage_type",
        "expected_value":
            "Both",
    },
    {
        "label":
            "package price comparison after Basic selection",
        "context":
            make_context(
                FlowState.QUOTE_COVERAGE,
                service="Wedding",
                package="Basic",
            ),
        "message":
            "wait tell me price difference one more time",
        "expected_actions": {
            SemanticAction.PACKAGE_RECONSIDERATION,
        },
    },
    {
        "label":
            "bare okay during package reconfirmation",
        "context":
            make_context(
                FlowState.PACKAGE_RECONFIRMATION,
                service="Wedding",
                package="Basic",
            ),
        "message":
            "okay",
        "expected_actions": {
            SemanticAction.PAUSE,
        },
    },
    {
        "label":
            "package switch during reconfirmation",
        "context":
            make_context(
                FlowState.PACKAGE_RECONFIRMATION,
                service="Wedding",
                package="Basic",
            ),
        "message":
            "premium kardo",
        "expected_actions": {
            SemanticAction.SWITCH_PACKAGE,
        },
        "expected_value":
            "Premium",
    },
    {
        "label":
            "natural affirmative in travel state",
        "context":
            make_context(
                FlowState.QUOTE_TRAVEL,
                service="Wedding",
                package="Premium",
                coverage_type="Both",
            ),
        "message":
            "okay kardo",
        "expected_actions": {
            SemanticAction.FIELD_VALUE,
        },
        "expected_field":
            "travel_required",
        "expected_value":
            "Yes",
    },
    {
        "label":
            "travel uncertainty",
        "context":
            make_context(
                FlowState.QUOTE_TRAVEL,
                service="Wedding",
                package="Premium",
                coverage_type="Both",
            ),
        "message":
            "maybe",
        "expected_actions": {
            SemanticAction.UNCLEAR,
        },
    },
    {
        "label":
            "location must not imply travel",
        "context":
            make_context(
                FlowState.QUOTE_TRAVEL,
                service="Wedding",
                package="Premium",
                coverage_type="Both",
            ),
        "message":
            "Birmingham",
        "expected_actions": {
            SemanticAction.UNCLEAR,
            SemanticAction.PAUSE,
        },
        "forbidden_value":
            "Yes",
    },
    {
        "label":
            "Telugu-English coverage selection",
        "context":
            make_context(
                FlowState.QUOTE_COVERAGE,
                service="Birthday",
                package="Basic",
            ),
        "message":
            "rendu kavali",
        "expected_actions": {
            SemanticAction.FIELD_VALUE,
        },
        "expected_field":
            "coverage_type",
        "expected_value":
            "Both",
    },
    {
        "label":
            "Hindi negative travel answer",
        "context":
            make_context(
                FlowState.QUOTE_TRAVEL,
                service="Birthday",
                package="Basic",
                coverage_type="Photography",
            ),
        "message":
            "nahi chahiye",
        "expected_actions": {
            SemanticAction.FIELD_VALUE,
        },
        "expected_field":
            "travel_required",
        "expected_value":
            "No",
    },
    {
        "label":
            "business question in duration state",
        "context":
            make_context(
                FlowState.QUOTE_DURATION,
                service="Wedding",
                package="Premium",
                coverage_type="Both",
                travel_required="No",
            ),
        "message":
            "do you provide drone?",
        "expected_actions": {
            SemanticAction.BUSINESS_QUESTION,
        },
    },
    {
        "label":
            "ready to review deferred field",
        "context":
            make_context(
                FlowState.DEFERRED_REVIEW,
                service="Wedding",
                package="Premium",
                coverage_type="Both",
                duration_hours=8,
                event_date="12 October",
                location="Birmingham",
                deferred_fields=[
                    "travel_required",
                ],
            ),
        "message":
            "okay kardo",
        "expected_actions": {
            SemanticAction.START_DEFERRED_REVIEW,
        },
    },
]


print()
print("=" * 72)
print("V3 BLOCK 4 - LIVE GEMINI SEMANTIC SMOKE TEST")
print("=" * 72)
print(
    "MODEL:",
    adapter.model_name,
)
print(
    "CASES:",
    len(cases),
)
print()
print(
    "This test calls Gemini but does not call Instagram, Gmail, "
    "Google Sheets, or Cloud Run."
)

passed = 0
failed = 0

for index, case in enumerate(
    cases,
    start=1,
):
    ok = run_case(
        index,
        **case,
    )

    if ok:
        passed += 1
    else:
        failed += 1

    # Keep requests polite to the API while remaining quick.
    if index < len(cases):
        time.sleep(0.4)


print()
print("=" * 72)
print("LIVE GEMINI SMOKE TEST SUMMARY")
print("=" * 72)
print(
    "PASSED:",
    passed,
)
print(
    "FAILED:",
    failed,
)
print(
    "TOTAL:",
    len(cases),
)

if failed:
    print()
    print(
        "V3 BLOCK 4 LIVE GEMINI SMOKE TEST FAILED"
    )
    print(
        "Do NOT connect V3 to Instagram yet."
    )
    sys.exit(1)

print()
print(
    "V3 BLOCK 4 LIVE GEMINI SMOKE TEST PASSED"
)
print(
    "Gemini respected the state-specific semantic contract "
    "for all live smoke cases."
)
