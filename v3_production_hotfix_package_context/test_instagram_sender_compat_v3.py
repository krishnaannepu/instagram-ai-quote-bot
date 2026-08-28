from customer_response_renderer_v3 import (
    ButtonSpec,
    RenderedMessage,
)
from instagram_sender_v3 import (
    ExistingInstagramServiceSenderV3,
)


class FakeInstagramService:
    calls = []

    @classmethod
    def send_instagram_menu(
        cls,
        recipient_id,
        menu,
    ):
        cls.calls.append(
            {
                "recipient_id":
                    recipient_id,
                "menu":
                    menu,
            }
        )

        return {
            "message_id":
                "fake-1"
        }


sender = ExistingInstagramServiceSenderV3(
    service_module=
        FakeInstagramService
)

sender.send_rendered(
    recipient_id="customer-123",
    message=RenderedMessage(
        text="Choose one",
        buttons=[
            ButtonSpec(
                label="Yes",
                payload="EMAIL_YES",
            ),
            ButtonSpec(
                label="No",
                payload="EMAIL_NO",
            ),
        ],
    ),
)

assert len(
    FakeInstagramService.calls
) == 1

call = FakeInstagramService.calls[0]

assert call[
    "recipient_id"
] == "customer-123"

assert call[
    "menu"
] == {
    "message":
        "Choose one",
    "options": [
        {
            "title":
                "Yes",
            "payload":
                "EMAIL_YES",
        },
        {
            "title":
                "No",
            "payload":
                "EMAIL_NO",
        },
    ],
}

print(
    "PASS 1 - V3 sender matches current send_instagram_menu transport"
)

print()
print("=" * 72)
print("V3 INSTAGRAM TRANSPORT COMPATIBILITY TEST PASSED")
print("=" * 72)
