from __future__ import annotations

import sys
from pathlib import Path
from typing import Protocol

from customer_response_renderer_v3 import RenderedMessage


class InstagramSender(Protocol):
    def send_rendered(
        self,
        *,
        recipient_id: str,
        message: RenderedMessage,
    ) -> None:
        ...


class ExistingInstagramServiceSenderV3:
    """
    Adapter over the existing instagram_service.py.

    The current production transport exposes `send_instagram_menu`, so V3
    renders its channel-independent message back into that stable transport
    shape.
    """

    def __init__(
        self,
        *,
        project_root: Path | None = None,
        service_module=None,
    ):
        self.project_root = (
            Path(project_root).resolve()
            if project_root
            else Path(__file__).resolve().parent.parent
        )
        self._service_module = (
            service_module
        )

    def _service(
        self,
    ):
        if self._service_module is not None:
            return self._service_module

        root = str(
            self.project_root
        )

        if root not in sys.path:
            sys.path.insert(
                0,
                root,
            )

        import instagram_service

        self._service_module = (
            instagram_service
        )

        return self._service_module

    def send_rendered(
        self,
        *,
        recipient_id: str,
        message: RenderedMessage,
    ) -> None:
        service = self._service()

        # Preferred compatibility path for the current production service.
        if hasattr(
            service,
            "send_instagram_menu",
        ):
            service.send_instagram_menu(
                recipient_id=recipient_id,
                menu={
                    "message":
                        message.text,
                    "options": [
                        {
                            "title":
                                button.label,
                            "payload":
                                button.payload,
                        }
                        for button in message.buttons
                    ],
                },
            )

            return

        # Secondary compatibility paths for future transport refactors.
        if (
            message.buttons
            and hasattr(
                service,
                "send_instagram_quick_replies",
            )
        ):
            service.send_instagram_quick_replies(
                recipient_id,
                message.text,
                [
                    {
                        "content_type": "text",
                        "title": button.label,
                        "payload": button.payload,
                    }
                    for button in message.buttons
                ],
            )

            return

        if hasattr(
            service,
            "send_instagram_message",
        ):
            service.send_instagram_message(
                recipient_id,
                message.text,
            )

            return

        if hasattr(
            service,
            "send_message",
        ):
            service.send_message(
                recipient_id,
                message.text,
            )

            return

        raise RuntimeError(
            "Existing instagram_service.py does not expose "
            "a supported send function."
        )
