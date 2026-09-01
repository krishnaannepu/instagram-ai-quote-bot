from pathlib import Path

main = Path("main.py").read_text(encoding="utf-8")

assert "def build_post_quote_options_menu()" in main

start = main.index(
    "def build_post_quote_options_menu()"
)
end = main.index(
    "def build_post_callback_options_menu()",
    start,
)

post_quote = main[start:end]

assert '"title": "Speak to Team"' in post_quote
assert '"title": "Start New Quote"' in post_quote
assert '"title": "Finish"' in post_quote
assert "You can speak to our team for more help" in post_quote

# Post-callback menu must still omit Speak to Team.
cb_start = main.index(
    "def build_post_callback_options_menu()"
)
cb_end = main.index(
    "def build_callback_already_recorded_menu()",
    cb_start,
)

post_callback = main[cb_start:cb_end]

assert '"title": "Speak to Team"' not in post_callback
assert '"title": "Start New Quote"' in post_callback
assert '"title": "Finish"' in post_callback

# Email/no-email/post-quote paths should now use the explicit menu.
assert "menu=build_post_quote_options_menu()" in main

print("POST-QUOTE BUTTON MENU TEST PASSED")
print("Post quote: Speak to Team / Start New Quote / Finish")
print("Post callback: Start New Quote / Finish")
