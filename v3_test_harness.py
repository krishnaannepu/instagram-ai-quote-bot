"""
Shared test harness for V3 regressions.

ScriptedAdapter runs canned Gemini JSON through the REAL
GeminiSemanticAdapter.parse_response(), so every production validation gate
runs in tests.

This exists because a hand-rolled fake that only mirrored the allowed-action
check let a second gate (FIELD_VALUE requiring an expected field) reach
production unnoticed. If a test double skips a gate, the gate is untested.
"""

from business_knowledge_adapter_v3 import BusinessKnowledgeAdapterV3
from conversation_orchestrator import ConversationOrchestrator
from gemini_semantic_adapter import GeminiSemanticAdapter


class FakeKnowledge:
    """Two services so a service change can strand a package."""

    SERVICES = {
        "Wedding": [("Basic", 4, 500, 650, 950, 80),
                    ("Premium", 6, 700, 850, 1200, 100)],
        "Birthday": [("Basic", 3, 300, 400, 600, 60),
                     ("Deluxe", 5, 550, 700, 1000, 90)],
    }

    @classmethod
    def get_business_knowledge(cls, force_refresh=False):
        return {
            "pricing": [
                {
                    "service": service,
                    "package": name,
                    "included_hours": inc,
                    "photography_price": photo,
                    "videography_price": video,
                    "both_price": both,
                    "extra_hour_rate": extra,
                    "travel_fee": 0,
                }
                for service, rows in cls.SERVICES.items()
                for name, inc, photo, video, both, extra in rows
            ],
            "packages": [],
            "business_info": [],
            "faqs": [],
        }


class ScriptedAdapter(GeminiSemanticAdapter):
    """
    The real adapter with the network call replaced by a queue of canned
    Gemini responses. Every validation and degrade path still runs.
    """

    def __init__(self, responses):
        super().__init__(client=None)
        self.responses = list(responses)

    def interpret(self, context, message_text, **kwargs):
        if not self.responses:
            raise AssertionError(
                f"No scripted Gemini response remains for {message_text!r}"
            )

        return self.parse_response(
            context,
            self.responses.pop(0),
        )


def gemini(action, **fields):
    """One canned Gemini JSON response."""

    payload = {
        "action": action,
        "language": "English",
        "confidence": 0.95,
    }
    payload.update(fields)

    return payload


def build_orchestrator(responses, knowledge=FakeKnowledge):
    catalogue = BusinessKnowledgeAdapterV3(
        service_module=knowledge
    ).get_catalogue()

    return ConversationOrchestrator(
        semantic_interpreter=ScriptedAdapter(responses),
        supported_services=catalogue["supported_services"],
        packages_by_service=catalogue["packages_by_service"],
    )
