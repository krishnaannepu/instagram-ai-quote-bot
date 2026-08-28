from __future__ import annotations

from dataclasses import dataclass

from instagram_sender_v3 import InstagramSender
from local_conversation_runtime_v3 import LocalConversationRuntimeV3
from meta_webhook_parser_v3 import (
    IncomingMessageType,
    MetaWebhookParserV3,
)
from session_repository_v3 import SessionRepository


@dataclass
class WebhookProcessingResult:
    processed_messages: int
    ignored_messages: int


class InstagramChannelAdapterV3:
    """
    Thin Instagram channel/controller layer.

    No quote, email, handoff, or callback routing lives here.
    """

    def __init__(
        self,
        *,
        runtime: LocalConversationRuntimeV3,
        session_repository: SessionRepository,
        sender: InstagramSender,
        parser: MetaWebhookParserV3 | None = None,
    ):
        self.runtime = runtime
        self.session_repository = (
            session_repository
        )
        self.sender = sender
        self.parser = (
            parser
            or MetaWebhookParserV3()
        )

    def process_webhook(
        self,
        payload: dict,
    ) -> WebhookProcessingResult:
        messages = self.parser.parse(
            payload
        )

        processed = 0
        ignored = 0

        for incoming in messages:
            context = (
                self.session_repository
                .get(
                    incoming.sender_id
                )
            )

            message_id = str(
                incoming.message_id
                or ""
            )

            # Small in-memory idempotency guard. Durable message dedupe belongs
            # in the later persistent repository hardening phase.
            if (
                message_id
                and context.metadata.get(
                    "last_processed_message_id"
                )
                == message_id
            ):
                ignored += 1
                continue

            context.metadata[
                "sender_id"
            ] = incoming.sender_id

            context.metadata[
                "last_message_id"
            ] = message_id

            if (
                incoming.type
                == IncomingMessageType.TEXT
            ):
                result = (
                    self.runtime
                    .handle_text(
                        context=context,
                        message_text=
                            incoming.text
                            or "",
                    )
                )
            else:
                result = (
                    self.runtime
                    .handle_button(
                        context=context,
                        payload=
                            incoming.button_payload
                            or "",
                    )
                )

            # Mark the message after successful runtime processing.
            if message_id:
                context.metadata[
                    "last_processed_message_id"
                ] = message_id

            self.session_repository.save(
                incoming.sender_id,
                context,
            )

            for rendered in result.messages:
                self.sender.send_rendered(
                    recipient_id=
                        incoming.sender_id,
                    message=
                        rendered,
                )

            processed += 1

        return WebhookProcessingResult(
            processed_messages=
                processed,
            ignored_messages=
                ignored,
        )
