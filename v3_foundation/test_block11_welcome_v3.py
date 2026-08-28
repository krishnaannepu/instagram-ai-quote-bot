from conversation_models import ConversationContext, FlowState
from conversation_orchestrator import ConversationOrchestrator
from customer_response_renderer_v3 import CustomerResponseRendererV3
from semantic_contract import SemanticAction, SemanticInterpretation


class GreetingInterpreter:
    def interpret(
        self,
        context,
        message_text,
        **kwargs,
    ):
        return SemanticInterpretation(
            action=SemanticAction.GREETING,
            confidence=0.99,
            language="English",
        )


orchestrator = ConversationOrchestrator(
    semantic_interpreter=GreetingInterpreter()
)

context = ConversationContext()

result = orchestrator.handle_text(
    context=context,
    message_text="Hi",
)

assert context.state == FlowState.IDLE
assert result.response_plan.action.value == "WELCOME"

rendered = CustomerResponseRendererV3().render_plan(
    result.response_plan
)

assert "How can we help" in rendered.text

payloads = [
    button.payload
    for button in rendered.buttons
]

assert payloads == [
    "GET_QUOTE",
    "SPEAK_TO_TEAM",
]

print("PASS 1 - first-time greeting stays in IDLE and renders welcome actions")


quote_start = orchestrator.handle_button(
    context=context,
    payload="GET_QUOTE",
)

assert context.state == FlowState.QUOTE_SERVICE
assert quote_start.response_plan.next_field == "service"

print("PASS 2 - welcome Get a Quote button enters authoritative quote state")

print()
print("=" * 72)
print("V3 BLOCK 11 WELCOME FLOW TEST PASSED")
print("=" * 72)
