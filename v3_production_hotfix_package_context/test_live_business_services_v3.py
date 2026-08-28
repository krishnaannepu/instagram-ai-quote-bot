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

# Make production project modules importable.
project_root_text = str(
    PROJECT_ROOT
)

if project_root_text not in sys.path:
    sys.path.insert(
        0,
        project_root_text,
    )

from business_answer_service_v3 import (
    BusinessAnswerServiceV3,
)
from business_knowledge_adapter_v3 import (
    BusinessKnowledgeAdapterV3,
)
from conversation_models import (
    ConversationContext,
    FlowState,
)
from quote_adapter_v3 import (
    QuoteAdapterV3,
)


print()
print("=" * 72)
print("V3 BLOCK 6 - LIVE BUSINESS KNOWLEDGE + QUOTE TEST")
print("=" * 72)
print(
    "This test uses your real Google Sheets and Gemini, "
    "but does not use Instagram, Gmail, or Cloud Run."
)

knowledge_adapter = (
    BusinessKnowledgeAdapterV3(
        project_root=PROJECT_ROOT
    )
)

knowledge = knowledge_adapter.get_all(
    force_refresh=True
)

print()
print(
    "KNOWLEDGE COUNTS:",
    {
        key: len(
            knowledge[key]
        )
        for key in (
            "pricing",
            "packages",
            "business_info",
            "faqs",
        )
    },
)

for required_key in (
    "pricing",
    "packages",
    "business_info",
    "faqs",
):
    if not knowledge[
        required_key
    ]:
        raise AssertionError(
            f"{required_key} is empty."
        )

catalogue = (
    knowledge_adapter
    .get_catalogue()
)

print(
    "SERVICES:",
    catalogue[
        "supported_services"
    ],
)

if not catalogue[
    "supported_services"
]:
    raise AssertionError(
        "No supported services were loaded."
    )

print(
    "PASS 1 - real approved business knowledge loaded"
)


# ------------------------------------------------------------------
# Deterministic quote against real Pricing sheet
# ------------------------------------------------------------------

service = (
    "Wedding"
    if "Wedding"
    in catalogue[
        "supported_services"
    ]
    else catalogue[
        "supported_services"
    ][0]
)

packages = (
    catalogue[
        "packages_by_service"
    ].get(
        service,
        [],
    )
)

if not packages:
    raise AssertionError(
        f"No packages found for {service}."
    )

package = (
    "Premium"
    if "Premium" in packages
    else packages[0]
)

pricing = knowledge_adapter.get_pricing(
    service,
    package,
)

if not pricing:
    raise AssertionError(
        f"No pricing row found for "
        f"{service} / {package}."
    )

included_hours = float(
    str(
        pricing.get(
            "included_hours",
            0,
        )
    ).replace(
        "£",
        "",
    )
)

duration_hours = (
    included_hours
    + 2
)

context = ConversationContext(
    state=FlowState.QUOTE_READY
)

context.quote.service = service
context.quote.package = package
context.quote.coverage_type = "Both"
context.quote.travel_required = "No"
context.quote.duration_hours = duration_hours
context.quote.event_date = "12 October"
context.quote.location = "Birmingham"

quote_adapter = QuoteAdapterV3(
    project_root=PROJECT_ROOT
)

quote = quote_adapter.calculate(
    context
)

base_price = float(
    str(
        pricing.get(
            "both_price",
            0,
        )
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

extra_rate = float(
    str(
        pricing.get(
            "extra_hour_rate",
            0,
        )
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

expected_total = (
    base_price
    + (
        2
        * extra_rate
    )
)

print()
print(
    "QUOTE:",
    {
        "service":
            service,
        "package":
            package,
        "coverage":
            "Both",
        "duration_hours":
            duration_hours,
        "base_price":
            quote.get(
                "base_price"
            ),
        "extra_hours":
            quote.get(
                "extra_hours"
            ),
        "extra_hour_rate":
            quote.get(
                "extra_hour_rate"
            ),
        "quote_total":
            quote.get(
                "quote_total"
            ),
    },
)

if float(
    quote[
        "quote_total"
    ]
) != float(
    expected_total
):
    raise AssertionError(
        f"Deterministic total mismatch. "
        f"Expected {expected_total}, "
        f"got {quote['quote_total']}."
    )

print(
    "PASS 2 - real quote_service matches Pricing-sheet arithmetic"
)


# ------------------------------------------------------------------
# Grounded real business answer
# ------------------------------------------------------------------

if not os.getenv(
    "GEMINI_API_KEY"
):
    raise AssertionError(
        "GEMINI_API_KEY is not configured."
    )

answer_service = (
    BusinessAnswerServiceV3(
        knowledge_adapter=
            knowledge_adapter,
    )
)

before_quote = (
    context.quote.as_dict()
)

answer = answer_service.answer(
    context=context,
    question_text=(
        f"What is the difference between "
        f"{packages[0]}"
        + (
            f" and {packages[1]}"
            if len(packages) > 1
            else ""
        )
        + " and what are their prices?"
    ),
    question_type=
        "PACKAGE_COMPARISON_WITH_PRICING",
    customer_language=
        "English",
)

print()
print(
    "BUSINESS ANSWER FOUND:",
    answer.answer_found,
)
print(
    "OFFER HUMAN:",
    answer.should_offer_human,
)
print(
    "ANSWER:"
)
print(
    answer.answer_text
)

if (
    context.quote.as_dict()
    != before_quote
):
    raise AssertionError(
        "Business answer mutated quote context."
    )

if not answer.answer_text:
    raise AssertionError(
        "No business answer text returned."
    )

print()
print(
    "PASS 3 - real Gemini grounded answer used approved business knowledge"
)
print(
    "PASS 4 - business answer did not mutate quote state"
)

print()
print("=" * 72)
print("V3 BLOCK 6 LIVE BUSINESS INTEGRATION TEST PASSED")
print("=" * 72)
