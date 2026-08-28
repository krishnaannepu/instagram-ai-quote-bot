from __future__ import annotations

import ast
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
main_path = BASE_DIR / "main.py"
source = main_path.read_text(
    encoding="utf-8"
)

tree = ast.parse(
    source
)

# ------------------------------------------------------------------
# 1. Legacy conversation-control symbols are not used by main.py.
# ------------------------------------------------------------------

for forbidden in [
    "current_stage",
    "expected_quote_field",
    "process_ai_customer_message",
    "process_session_button",
    "complete_quote",
    "process_handoff_request",
    "start_callback_request",
    "send_customer_quote_email",
]:
    assert forbidden not in source, (
        f"Legacy conversation symbol remains in main.py: {forbidden}"
    )

print("PASS 1 - final main.py contains no legacy conversation router")


# ------------------------------------------------------------------
# 2. Only one V3 channel delegation controls POST webhook.
# ------------------------------------------------------------------

assert "get_v3_channel()" in source
assert ".process_webhook(" in source
assert "conversation_engine" in source

print("PASS 2 - POST webhook delegates to V3 channel adapter")


# ------------------------------------------------------------------
# 3. Preserve all public endpoints.
# ------------------------------------------------------------------

routes = []

for node in ast.walk(tree):
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call):
                continue

            func = decorator.func

            if not (
                isinstance(func, ast.Attribute)
                and isinstance(func.value, ast.Name)
                and func.value.id == "app"
            ):
                continue

            if not decorator.args:
                continue

            route_arg = decorator.args[0]

            if isinstance(route_arg, ast.Constant):
                routes.append(
                    (
                        func.attr,
                        route_arg.value,
                    )
                )

expected = {
    ("get", "/"),
    ("get", "/privacy-policy"),
    ("get", "/terms"),
    ("get", "/data-deletion"),
    ("get", "/instagram/webhook"),
    ("get", "/instagram/callback"),
    ("post", "/instagram/webhook"),
}

assert set(routes) == expected, routes

print("PASS 3 - health/legal/verification/callback/webhook routes are preserved")


# ------------------------------------------------------------------
# 4. Runtime construction is lazy.
# ------------------------------------------------------------------

assert "_v3_channel = None" in source
assert "def get_v3_channel" in source

print("PASS 4 - downstream integrations are initialized lazily")


print()
print("=" * 72)
print("V3 BLOCK 11 MAIN CUTOVER CONTRACT TEST PASSED")
print("=" * 72)
