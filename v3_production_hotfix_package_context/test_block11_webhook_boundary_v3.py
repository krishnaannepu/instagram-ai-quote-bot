from dataclasses import dataclass

from customer_response_renderer_v3 import RenderedMessage
from instagram_channel_adapter_v3 import InstagramChannelAdapterV3
from meta_webhook_parser_v3 import MetaWebhookParserV3
from session_repository_v3 import InMemorySessionRepositoryV3


@dataclass
class FakeRuntimeResult:
    messages: list
    quote: dict | None = None
    turn_log: dict | None = None


class FakeRuntime:
    def __init__(self):
        self.calls = []

    def handle_text(
        self,
        *,
        context,
        message_text,
    ):
        self.calls.append(
            (
                "text",
                message_text,
            )
        )

        return FakeRuntimeResult(
            messages=[
                RenderedMessage(
                    text=f"TEXT:{message_text}"
                )
            ]
        )

    def handle_button(
        self,
        *,
        context,
        payload,
    ):
        self.calls.append(
            (
                "button",
                payload,
            )
        )

        return FakeRuntimeResult(
            messages=[
                RenderedMessage(
                    text=f"BUTTON:{payload}"
                )
            ]
        )


class CapturingSender:
    def __init__(self):
        self.sent = []

    def send_rendered(
        self,
        *,
        recipient_id,
        message,
    ):
        self.sent.append(
            (
                recipient_id,
                message.text,
            )
        )


runtime = FakeRuntime()
sessions = InMemorySessionRepositoryV3()
sender = CapturingSender()

channel = InstagramChannelAdapterV3(
    runtime=runtime,
    session_repository=sessions,
    sender=sender,
    parser=MetaWebhookParserV3(
        ignored_sender_id="business-999"
    ),
)


def text_payload(
    sender_id,
    message_id,
    text,
):
    return {
        "object": "instagram",
        "entry": [
            {
                "messaging": [
                    {
                        "sender": {
                            "id": sender_id
                        },
                        "recipient": {
                            "id": "business-999"
                        },
                        "message": {
                            "mid": message_id,
                            "text": text,
                        },
                    }
                ]
            }
        ],
    }


def button_payload(
    sender_id,
    message_id,
    payload,
):
    return {
        "object": "instagram",
        "entry": [
            {
                "messaging": [
                    {
                        "sender": {
                            "id": sender_id
                        },
                        "recipient": {
                            "id": "business-999"
                        },
                        "message": {
                            "mid": message_id,
                            "text": "button",
                            "quick_reply": {
                                "payload": payload,
                            },
                        },
                    }
                ]
            }
        ],
    }


first = channel.process_webhook(
    text_payload(
        "customer-1",
        "m-1",
        "Hi",
    )
)

assert first.processed_messages == 1
assert first.ignored_messages == 0
assert runtime.calls == [
    (
        "text",
        "Hi",
    )
]
assert sender.sent[-1] == (
    "customer-1",
    "TEXT:Hi",
)

print("PASS 1 - customer text payload reaches V3 runtime")


duplicate = channel.process_webhook(
    text_payload(
        "customer-1",
        "m-1",
        "Hi",
    )
)

assert duplicate.processed_messages == 0
assert duplicate.ignored_messages == 1
assert len(runtime.calls) == 1

print("PASS 2 - duplicate Meta message id is ignored in-memory")


button = channel.process_webhook(
    button_payload(
        "customer-1",
        "m-2",
        "GET_QUOTE",
    )
)

assert button.processed_messages == 1
assert runtime.calls[-1] == (
    "button",
    "GET_QUOTE",
)

print("PASS 3 - quick reply payload reaches the same V3 channel path")


outgoing = channel.process_webhook(
    text_payload(
        "business-999",
        "m-business",
        "outgoing business message",
    )
)

assert outgoing.processed_messages == 0
assert len(runtime.calls) == 2

print("PASS 4 - outgoing business sender is ignored")


echo = {
    "entry": [
        {
            "messaging": [
                {
                    "sender": {
                        "id": "customer-1"
                    },
                    "message": {
                        "mid": "echo-1",
                        "text": "echo",
                        "is_echo": True,
                    },
                }
            ]
        }
    ]
}

echo_result = channel.process_webhook(
    echo
)

assert echo_result.processed_messages == 0

print("PASS 5 - explicit Meta echo is ignored")

print()
print("=" * 72)
print("V3 BLOCK 11 WEBHOOK BOUNDARY TEST PASSED")
print("=" * 72)
