from pathlib import Path

main_text = Path(
    "main.py"
).read_text(
    encoding="utf-8"
)

checks = [
    (
        "dedicated post-callback menu exists",
        "def build_post_callback_options_menu()" in main_text,
    ),
    (
        "post-callback menu has Start New Quote",
        '"title": "Start New Quote"' in main_text,
    ),
    (
        "post-callback menu has Finish",
        '"title": "Finish"' in main_text,
    ),
    (
        "callback success uses dedicated menu",
        'menu=build_post_callback_options_menu()'
        in main_text,
    ),
    (
        "callback-recorded free text still reaches AI",
        '"CALLBACK_RECORDED"' in main_text
        and "Non-acknowledgement messages are allowed to fall through"
        in main_text,
    ),
]

for name, passed in checks:
    print(
        f"{name}: "
        f"{'PASS' if passed else 'FAIL'}"
    )
    assert passed, name

# Inspect only the dedicated menu function text to ensure it does not
# accidentally expose a Speak to Team button.
start = main_text.index(
    "def build_post_callback_options_menu()"
)

end = main_text.index(
    "def build_callback_already_recorded_menu()",
    start,
)

menu_function = main_text[
    start:end
]

assert (
    '"title": "Speak to Team"'
    not in menu_function
)

assert (
    '"payload": "SPEAK_TO_TEAM"'
    not in menu_function
)

print()
print(
    "POST-CALLBACK FLOW REGRESSION TEST PASSED"
)
