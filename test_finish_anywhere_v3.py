"""
Ending the conversation must always work.

A customer who says stop and is not listened to is the worst failure this bot
can have, so it does not depend on the model being available or on which state
the conversation is in. An exact whole-message match ends the chat before the
semantic layer, before the deterministic phone and email parsers, everywhere.

Gemini still handles the phrasings a list cannot cover; the prompt teaches it
FINISH separately. This suite covers the guaranteed path.
"""

from conversation_models import ConversationContext, FlowState
from customer_response_renderer_v3 import CustomerResponseRendererV3
from v3_test_harness import build_orchestrator

renderer = CustomerResponseRendererV3()

STATES = [state for state in FlowState if state != FlowState.BUSINESS_INTERRUPT]

ENDS_THE_CHAT = [
    "stop", "Stop", "  STOP  ", "stop please",
    "finish", "Finished", "im done", "I'm done", "I am done",
    "that's all", "that\u2019s all", "thats it", "nothing else",
    "cancel", "cancel it", "end chat", "exit", "quit", "close chat",
    "bye", "BYE!!", "goodbye", "ok bye", "thanks bye",
    "bas", "bas karo", "khatam", "band karo",
]

# Superstrings and near misses. Ending someone's conversation by accident is
# worse than making them say it again.
MUST_NOT_END = [
    "don't stop",
    "stop by the studio",
    "can we finish tomorrow instead",
    "finishing touches",
    "wait",
    "hold on",
    "one moment",
    "is there a bus stop nearby",
    "no",
]


# 1 -----------------------------------------------------------------
# Works in every state, with no Gemini available at all.
failures = []

for state in STATES:
    context = ConversationContext()
    context.state = state
    context.quote.service = "Wedding"
    context.quote.package = "Basic"

    # An empty response queue means any call to Gemini raises.
    orchestrator = build_orchestrator([])

    try:
        turn = orchestrator.handle_text(context=context, message_text="stop")
    except Exception as error:
        failures.append((state.value, f"{type(error).__name__}: {error}"))
        continue

    if context.state != FlowState.FINISHED:
        failures.append((state.value, f"ended in {context.state.value}"))
        continue

    if not renderer.render_plan(turn.response_plan).text.strip():
        failures.append((state.value, "no closing message"))

if failures:
    print(f"{len(failures)} states did not end:")
    for state, message in failures:
        print(f"  {state:24} {message}")

assert not failures, "stop must end the conversation from every state"
print(f"PASS - 'stop' ends the conversation from all {len(STATES)} states, "
      f"without Gemini")


# 2 -----------------------------------------------------------------
missed = []

for message_text in ENDS_THE_CHAT:
    context = ConversationContext()
    context.state = FlowState.QUOTE_TRAVEL
    context.quote.service = "Wedding"

    orchestrator = build_orchestrator([])

    try:
        orchestrator.handle_text(context=context, message_text=message_text)
    except Exception:
        missed.append(message_text)
        continue

    if context.state != FlowState.FINISHED:
        missed.append(message_text)

if missed:
    print("phrasings that did not end the chat:")
    for message_text in missed:
        print(f"  {message_text!r}")

assert not missed, "every listed phrasing must end the conversation"
print(f"PASS - all {len(ENDS_THE_CHAT)} phrasings end the conversation")


# 3 -----------------------------------------------------------------
wrongly_ended = []

for message_text in MUST_NOT_END:
    context = ConversationContext()
    context.state = FlowState.QUOTE_TRAVEL
    context.quote.service = "Wedding"

    orchestrator = build_orchestrator([{"action": "PAUSE"}])
    orchestrator.handle_text(context=context, message_text=message_text)

    if context.state == FlowState.FINISHED:
        wrongly_ended.append(message_text)

if wrongly_ended:
    print("messages that ended the chat and should not have:")
    for message_text in wrongly_ended:
        print(f"  {message_text!r}")

assert not wrongly_ended, (
    "ending someone's conversation by accident is worse than asking again"
)
print(f"PASS - {len(MUST_NOT_END)} near misses correctly left the chat open")


# 4 -----------------------------------------------------------------
# Ending mid-quote discards nothing the customer needs, and a greeting
# afterwards starts cleanly.
context = ConversationContext()
context.state = FlowState.QUOTE_DURATION
context.quote.service = "Wedding"
context.quote.package = "Basic"

orchestrator = build_orchestrator([])
orchestrator.handle_text(context=context, message_text="cancel")

assert context.state == FlowState.FINISHED

orchestrator = build_orchestrator([{"action": "GREETING"}])
turn = orchestrator.handle_text(context=context, message_text="Hi")

assert context.state == FlowState.IDLE
assert context.quote.service is None, "the abandoned quote must not linger"
print("PASS - ending mid-quote then greeting starts a clean conversation")


print()
print("=" * 72)
print("V3 FINISH ANYWHERE REGRESSION PASSED")
print("=" * 72)
