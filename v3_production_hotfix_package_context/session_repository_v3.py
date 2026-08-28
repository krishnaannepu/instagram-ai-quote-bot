from __future__ import annotations

from copy import deepcopy
from typing import Protocol

from conversation_models import ConversationContext


class SessionRepository(Protocol):
    def get(
        self,
        sender_id: str,
    ) -> ConversationContext:
        ...

    def save(
        self,
        sender_id: str,
        context: ConversationContext,
    ) -> None:
        ...

    def delete(
        self,
        sender_id: str,
    ) -> None:
        ...


class InMemorySessionRepositoryV3:
    """
    Temporary repository for local/webhook integration.

    This is intentionally NOT the final production persistence layer.
    Firestore should replace it after the channel cutover is stable.
    """

    def __init__(
        self,
    ):
        self._sessions: dict[
            str,
            ConversationContext,
        ] = {}

    def get(
        self,
        sender_id: str,
    ) -> ConversationContext:
        sender_id = str(
            sender_id
        )

        if sender_id not in self._sessions:
            self._sessions[
                sender_id
            ] = ConversationContext()

        return self._sessions[
            sender_id
        ]

    def save(
        self,
        sender_id: str,
        context: ConversationContext,
    ) -> None:
        self._sessions[
            str(sender_id)
        ] = context

    def delete(
        self,
        sender_id: str,
    ) -> None:
        self._sessions.pop(
            str(sender_id),
            None,
        )

    def count(
        self,
    ) -> int:
        return len(
            self._sessions
        )
