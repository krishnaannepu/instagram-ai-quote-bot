"""Compatibility facade for Conversation Engine V2.

Existing imports in ``main.py`` can keep using ``ai_conversation_service``
while the actual orchestration now lives in ``conversation_engine.py``.
"""

from conversation_engine import (
    QUOTE_FIELDS,
    REQUIRED_QUOTE_FIELDS,
    apply_customer_understanding,
    get_available_options_for_field,
    get_deferred_quote_fields,
    get_missing_quote_fields,
    get_next_missing_quote_field,
    get_next_quote_field_for_prompt,
    get_packages_for_service,
    get_supported_services,
    initialize_new_quote_flow,
    mark_flow_finished,
    process_ai_customer_message,
    quote_is_complete,
)

__all__ = [
    "QUOTE_FIELDS",
    "REQUIRED_QUOTE_FIELDS",
    "apply_customer_understanding",
    "get_available_options_for_field",
    "get_deferred_quote_fields",
    "get_missing_quote_fields",
    "get_next_missing_quote_field",
    "get_next_quote_field_for_prompt",
    "get_packages_for_service",
    "get_supported_services",
    "initialize_new_quote_flow",
    "mark_flow_finished",
    "process_ai_customer_message",
    "quote_is_complete",
]
