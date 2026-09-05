from __future__ import annotations

import os
from pathlib import Path

from business_answer_service_v3 import BusinessAnswerServiceV3
from business_knowledge_adapter_v3 import BusinessKnowledgeAdapterV3
from business_question_coordinator_v3 import BusinessQuestionCoordinatorV3
from conversation_orchestrator import ConversationOrchestrator
from customer_response_renderer_v3 import CustomerResponseRendererV3
from email_delivery_adapter_v3 import EmailDeliveryAdapterV3
from gemini_semantic_adapter import GeminiSemanticAdapter
from handoff_callback_service_v3 import HandoffCallbackServiceV3
from instagram_channel_adapter_v3 import InstagramChannelAdapterV3
from instagram_sender_v3 import ExistingInstagramServiceSenderV3
from meta_webhook_parser_v3 import MetaWebhookParserV3
from lead_persistence_adapter_v3 import LeadPersistenceAdapterV3
from local_conversation_runtime_v3 import LocalConversationRuntimeV3
from message_translator_v3 import MessageTranslatorV3
from quote_adapter_v3 import QuoteAdapterV3
from quote_completion_service_v3 import QuoteCompletionServiceV3
from session_repository_v3 import InMemorySessionRepositoryV3


def build_instagram_channel_v3(
    *,
    project_root: Path | None = None,
) -> InstagramChannelAdapterV3:
    project_root = (
        Path(project_root).resolve()
        if project_root
        else Path(__file__).resolve().parent.parent
    )

    knowledge = BusinessKnowledgeAdapterV3(
        project_root=project_root
    )

    catalogue = knowledge.get_catalogue()

    semantic = GeminiSemanticAdapter()

    orchestrator = ConversationOrchestrator(
        semantic_interpreter=semantic,
        supported_services=catalogue["supported_services"],
        packages_by_service=catalogue["packages_by_service"],
    )

    quote_adapter = QuoteAdapterV3(
        project_root=project_root
    )

    lead_persistence = LeadPersistenceAdapterV3(
        project_root=project_root
    )

    email_delivery = EmailDeliveryAdapterV3(
        project_root=project_root,
        lead_persistence=lead_persistence,
    )

    answer_service = BusinessAnswerServiceV3(
        knowledge_adapter=knowledge
    )

    coordinator = BusinessQuestionCoordinatorV3(
        orchestrator=orchestrator,
        answer_service=answer_service,
        quote_adapter=quote_adapter,
    )

    quote_completion = QuoteCompletionServiceV3(
        orchestrator=orchestrator,
        quote_adapter=quote_adapter,
        lead_persistence=lead_persistence,
        email_delivery=email_delivery,
    )

    handoff_service = HandoffCallbackServiceV3(
        lead_persistence=lead_persistence,
        email_delivery=email_delivery,
    )

    runtime = LocalConversationRuntimeV3(
        orchestrator=orchestrator,
        business_coordinator=coordinator,
        quote_completion=quote_completion,
        email_delivery=email_delivery,
        handoff_service=handoff_service,
        renderer=CustomerResponseRendererV3(),
        translator=MessageTranslatorV3(),
    )

    sender = ExistingInstagramServiceSenderV3(
        project_root=project_root
    )

    sessions = InMemorySessionRepositoryV3()

    parser = MetaWebhookParserV3(
        ignored_sender_id=os.getenv(
            "INSTAGRAM_BUSINESS_ID",
            "",
        )
    )

    return InstagramChannelAdapterV3(
        runtime=runtime,
        session_repository=sessions,
        sender=sender,
        parser=parser,
    )
