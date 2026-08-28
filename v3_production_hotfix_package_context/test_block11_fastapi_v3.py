from types import SimpleNamespace

from fastapi.testclient import TestClient

import main


class FakeChannel:
    def __init__(self):
        self.payloads = []

    def process_webhook(
        self,
        payload,
    ):
        self.payloads.append(
            payload
        )

        return SimpleNamespace(
            processed_messages=1,
            ignored_messages=0,
        )


fake_channel = FakeChannel()
main._v3_channel = fake_channel

client = TestClient(
    main.app
)


health = client.get(
    "/"
)

assert health.status_code == 200
assert health.json()[
    "conversation_engine"
] == "v3"

print("PASS 1 - health endpoint reports V3")


verification = client.get(
    "/instagram/webhook",
    params={
        "hub.mode":
            "subscribe",
        "hub.verify_token":
            main.VERIFY_TOKEN,
        "hub.challenge":
            "123456",
    },
)

assert verification.status_code == 200
assert verification.text == "123456"

print("PASS 2 - Meta webhook verification endpoint is preserved")


payload = {
    "object":
        "instagram",
    "entry": [
        {
            "messaging": [
                {
                    "sender": {
                        "id":
                            "customer-1"
                    },
                    "message": {
                        "mid":
                            "m1",
                        "text":
                            "Hi",
                    },
                }
            ]
        }
    ],
}

response = client.post(
    "/instagram/webhook",
    json=payload,
)

assert response.status_code == 200
body = response.json()

assert body[
    "conversation_engine"
] == "v3"

assert body[
    "processed_messages"
] == 1

assert fake_channel.payloads == [
    payload
]

print("PASS 3 - POST webhook delegates raw payload to V3 channel")


for route in [
    "/privacy-policy",
    "/terms",
    "/data-deletion",
]:
    result = client.get(
        route
    )

    assert result.status_code == 200

print("PASS 4 - public legal endpoints remain available")


callback_missing = client.get(
    "/instagram/callback"
)

assert callback_missing.status_code == 400

callback_ok = client.get(
    "/instagram/callback",
    params={
        "code":
            "temporary-code"
    },
)

assert callback_ok.status_code == 200
assert callback_ok.json()[
    "status"
] == "authorization_received"

print("PASS 5 - Instagram login callback behavior is preserved")

print()
print("=" * 72)
print("V3 BLOCK 11 FASTAPI CUTOVER TEST PASSED")
print("=" * 72)
