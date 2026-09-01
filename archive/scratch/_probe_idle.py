from business_knowledge_adapter_v3 import BusinessKnowledgeAdapterV3
from conversation_models import ConversationContext, FlowState
from conversation_orchestrator import ConversationOrchestrator
from customer_response_renderer_v3 import CustomerResponseRendererV3
from semantic_contract import (SemanticAction, SemanticInterpretation,
                               is_action_allowed)

class FakeKnowledge:
    @staticmethod
    def get_business_knowledge(force_refresh=False):
        return {"pricing": [{"service": "Wedding", "package": "Basic",
                             "included_hours": 4, "photography_price": 500,
                             "videography_price": 650, "both_price": 950,
                             "extra_hour_rate": 80, "travel_fee": 0}],
                "packages": [], "business_info": [], "faqs": []}

class Gated:
    def __init__(self, m): self.m = list(m)
    def interpret(self, context, message_text, **kw):
        meaning = self.m.pop(0)
        if not is_action_allowed(context.state, meaning.action):
            raise RuntimeError(f"Action {meaning.action.value} is not allowed "
                               f"while state is {context.state.value}.")
        return meaning

def mk(a, **kw):
    return SemanticInterpretation(action=a, confidence=0.95, language="English", **kw)

cat = BusinessKnowledgeAdapterV3(service_module=FakeKnowledge).get_catalogue()
r = CustomerResponseRendererV3()

for label, meaning_obj in [
    ("FIELD_VALUE service=Wedding", mk(SemanticAction.FIELD_VALUE, field_name="service", value="Wedding")),
    ("CHANGE_FIELD service=Wedding", mk(SemanticAction.CHANGE_FIELD, field_name="service", value="Wedding")),
    ("STATUS_QUESTION",              mk(SemanticAction.STATUS_QUESTION, question_text="Wedding")),
    ("BUSINESS_QUESTION",            mk(SemanticAction.BUSINESS_QUESTION, question_text="Need service for wedding")),
    ("START_NEW_QUOTE",              mk(SemanticAction.START_NEW_QUOTE)),
]:
    orch = ConversationOrchestrator(semantic_interpreter=Gated([mk(SemanticAction.GREETING), meaning_obj]),
                                    supported_services=cat["supported_services"],
                                    packages_by_service=cat["packages_by_service"])
    ctx = ConversationContext()
    orch.handle_text(context=ctx, message_text="Hi")
    try:
        t = orch.handle_text(context=ctx, message_text="Wedding")
        print(f"  OK    {label:32} -> {r.render_plan(t.response_plan).text[:60]}")
    except Exception as e:
        print(f"  FAIL  {label:32} -> {e}")
