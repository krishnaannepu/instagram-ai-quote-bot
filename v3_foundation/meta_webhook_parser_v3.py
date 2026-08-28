from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class IncomingMessageType(str, Enum):
    TEXT = "TEXT"
    BUTTON = "BUTTON"


@dataclass(frozen=True)
class IncomingInstagramMessage:
    sender_id: str
    message_id: str | None
    type: IncomingMessageType
    text: str | None = None
    button_payload: str | None = None


class MetaWebhookParserV3:
    """
    Extract customer messages from Meta webhook payloads.

    Echoes, outgoing business messages, and malformed entries are ignored.
    """

    def __init__(
        self,
        *,
        ignored_sender_id: str | None = None,
    ):
        self.ignored_sender_id = str(
            ignored_sender_id
            or ""
        ).strip()

    def parse(
        self,
        payload: dict[str, Any],
    ) -> list[IncomingInstagramMessage]:
        messages: list[
            IncomingInstagramMessage
        ] = []

        for entry in payload.get(
            "entry",
            [],
        ):
            for messaging in entry.get(
                "messaging",
                [],
            ):
                message = (
                    messaging.get(
                        "message"
                    )
                    or {}
                )

                if not message:
                    continue

                if message.get(
                    "is_echo"
                ):
                    continue

                sender_id = str(
                    (
                        messaging.get(
                            "sender"
                        )
                        or {}
                    ).get(
                        "id",
                        "",
                    )
                ).strip()

                if not sender_id:
                    continue

                if (
                    self.ignored_sender_id
                    and sender_id
                    == self.ignored_sender_id
                ):
                    continue

                message_id = (
                    message.get(
                        "mid"
                    )
                )

                quick_reply = (
                    message.get(
                        "quick_reply"
                    )
                    or {}
                )

                payload_value = (
                    quick_reply.get(
                        "payload"
                    )
                )

                if payload_value:
                    messages.append(
                        IncomingInstagramMessage(
                            sender_id=
                                sender_id,
                            message_id=
                                message_id,
                            type=
                                IncomingMessageType
                                .BUTTON,
                            button_payload=
                                str(
                                    payload_value
                                ),
                        )
                    )
                    continue

                text = (
                    message.get(
                        "text"
                    )
                )

                if text is not None:
                    text = str(
                        text
                    ).strip()

                if text:
                    messages.append(
                        IncomingInstagramMessage(
                            sender_id=
                                sender_id,
                            message_id=
                                message_id,
                            type=
                                IncomingMessageType
                                .TEXT,
                            text=
                                text,
                        )
                    )

        return messages
