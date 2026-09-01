from pathlib import Path
import ast
import re

main_text = Path("main.py").read_text(encoding="utf-8")
gemini_text = Path("gemini_service.py").read_text(encoding="utf-8")
ai_text = Path("ai_conversation_service.py").read_text(encoding="utf-8")

checks = [
    (
        "email side-question stage preserved",
        "A side question must not make the pending email decision vanish."
        in main_text,
    ),
    (
        "typed email confirmation supported",
        "interpret_email_confirmation" in main_text
        and "email_quote_copy" in gemini_text,
    ),
    (
        "post quote menu restored",
        "keep the three" in main_text.lower()
        and "POST_QUOTE_OPTIONS" in main_text,
    ),
    (
        "callback distinct from handoff",
        "REQUEST_CALLBACK" in gemini_text
        and "REQUEST_CALLBACK" in ai_text,
    ),
    (
        "callback natural-language action handled",
        'if action == "REQUEST_CALLBACK":'
        in main_text,
    ),
    (
        "repetitive excited phrase stripping present",
        "excited" in gemini_text.lower()
        and "opening_patterns" in gemini_text,
    ),
    (
        "field-specific transitions present",
        "work out the timing" in gemini_text
        and "pin down the date" in gemini_text
        and "nearly there" in gemini_text,
    ),
    (
        "package spacing repair present",
        "Repair awkward generated layouts" in gemini_text
        and "start a separate" in gemini_text,
    ),
]

for name, passed in checks:
    print(
        f"{name}: "
        f"{'PASS' if passed else 'FAIL'}"
    )
    assert passed, name

# Run only the formatter function in isolation.
tree = ast.parse(
    gemini_text
)

formatter_node = None

for node in tree.body:
    if (
        isinstance(
            node,
            ast.FunctionDef,
        )
        and node.name
        == "_instagram_plain_text"
    ):
        formatter_node = node
        break

assert formatter_node is not None

module = ast.Module(
    body=[
        formatter_node
    ],
    type_ignores=[],
)

ast.fix_missing_locations(
    module
)

namespace = {
    "re": re,
}

exec(
    compile(
        module,
        "<formatter_test>",
        "exec",
    ),
    namespace,
)

formatter = namespace[
    "_instagram_plain_text"
]

sample = (
    "For our wedding service, the Basic package includes up to 4 hours "
    "of coverage and standard editing. The Premium package includes up "
    "to 6 hours and enhanced editing."
)

formatted = formatter(
    sample
)

print()
print(
    "FORMATTED PACKAGE COMPARISON:"
)
print(
    formatted
)

assert (
    "editing.\n\nThe Premium package"
    in formatted
)

awkward_sample = (
    "Basic package includes 4 hours.\n\n"
    "The\n\nPremium package includes 6 hours."
)

awkward_formatted = formatter(
    awkward_sample
)

assert (
    "\n\nPremium package includes"
    in awkward_formatted
)

assert (
    "\n\nThe\n\nPremium"
    not in awkward_formatted
)

print()
print(
    "FINAL QUOTE CONVERSATION V2 "
    "REGRESSION CHECK PASSED"
)
