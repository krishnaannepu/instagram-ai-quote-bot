from pathlib import Path
import ast
import collections

ROOT = Path(__file__).resolve().parent

FILES = [
    "conversation_state.py",
    "conversation_engine.py",
    "ai_conversation_service.py",
    "gemini_service.py",
    "main.py",
    "sheets_service.py",
    "business_knowledge_service.py",
    "instagram_service.py",
    "quote_service.py",
]

for filename in FILES:
    source = (ROOT / filename).read_text(encoding="utf-8")
    compile(source, str(ROOT / filename), "exec")

print("PASS - all V2 Python files compile")

for filename in [
    "conversation_state.py",
    "conversation_engine.py",
    "main.py",
    "sheets_service.py",
]:
    source = (ROOT / filename).read_text(encoding="utf-8")
    tree = ast.parse(source)
    names = [
        node.name
        for node in tree.body
        if isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
                ast.ClassDef,
            ),
        )
    ]
    duplicates = [
        name
        for name, count in collections.Counter(names).items()
        if count > 1
    ]
    assert not duplicates, (
        f"{filename} contains duplicate top-level definitions: "
        f"{duplicates}"
    )

print("PASS - no duplicate top-level definitions in core files")

state_source = (ROOT / "conversation_state.py").read_text(encoding="utf-8")
engine_source = (ROOT / "conversation_engine.py").read_text(encoding="utf-8")
main_source = (ROOT / "main.py").read_text(encoding="utf-8")
sheets_source = (ROOT / "sheets_service.py").read_text(encoding="utf-8")
facade_source = (ROOT / "ai_conversation_service.py").read_text(encoding="utf-8")

for state in [
    "QUOTE_SERVICE",
    "QUOTE_PACKAGE",
    "QUOTE_COVERAGE",
    "QUOTE_TRAVEL",
    "QUOTE_DURATION",
    "QUOTE_DATE",
    "QUOTE_LOCATION",
    "PACKAGE_RECONFIRMATION",
    "DEFERRED_REVIEW_READY",
    "QUOTE_READY",
]:
    assert state in state_source

print("PASS - authoritative FlowState model is present")

assert "resume_stack" in state_source
assert "transition_log" in state_source
assert "process_ai_customer_message" in engine_source
assert "fields_to_update" in engine_source
assert "resume_prompt" in engine_source
assert "initialize_new_quote_flow" in facade_source

print("PASS - interrupt/resume orchestration contract is present")

assert "def get_spreadsheet()" in sheets_source
assert "class _LazySpreadsheet" in sheets_source
assert sheets_source.count("def get_pricing_rule(") == 1

print("PASS - Sheets connection is lazy and pricing lookup is not duplicated")

assert '"flow_state": "IDLE"' in main_source
assert '"resume_stack": []' in main_source
assert "def send_ai_resume_prompt(" in main_source
assert "def build_post_quote_options_menu()" in main_source
assert "def build_post_callback_options_menu()" in main_source

print("PASS - main.py is wired to V2 state/resume behavior")

assert "ANSWER_BUSINESS_QUESTION_AND_RECONFIRM_PACKAGE" not in main_source
assert "ANSWER_BUSINESS_QUESTION_AND_RECONFIRM_PACKAGE" not in engine_source

print("PASS - old package-specific one-off action has been removed")

print()
print("=" * 72)
print("ARCHITECTURE V2 CONTRACT TEST PASSED")
print("=" * 72)
