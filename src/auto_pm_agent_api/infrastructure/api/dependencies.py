"""Dependency injection for API endpoints."""

import logging
import os
from functools import lru_cache
from dotenv import load_dotenv
from typing import Optional

from auto_pm_agent_api.application.chat_service import ChatService
from auto_pm_agent_api.application.project_management_service import ProjectManagementService
from auto_pm_agent_api.application.qa_service import QAService
from auto_pm_agent_api.application.assignment_service import AssignmentService
from auto_pm_agent_api.application.report_service import WorkReportExtractor
from auto_pm_agent_api.application.report_session import ReportSessionManager

from auto_pm_agent_api.infrastructure.llm_providers import LLMClient
from auto_pm_agent_api.infrastructure.db import RedisMemory
from auto_pm_agent_api.infrastructure.llm_providers import Router, GeneralBot
from auto_pm_agent_api.infrastructure.plane_client import PlaneAPIClient

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


class PlaneAPIFactory:
    """Factory for creating Plane API instances."""
    
    def __init__(self):
        """Initialize factory with default configuration."""
        self.base_url = os.getenv("PLANE_BASE_URL")
        self.api_key = os.getenv("PLANE_API_KEY")
        self.workspace_slug = os.getenv("PLANE_WORKSPACE_SLUG")
    
    def get_api(self, user_id: Optional[int] = None) -> PlaneAPIClient:
        """
        Get Plane API instance.
        
        Args:
            user_id: Optional[int] for user-specific configuration
            
        Returns:
            PlaneAPIClient instance
        """
        # In the future, you could customize API instance per user
        # For now, return a shared instance with workspace config
        return PlaneAPIClient(
            base_url=self.base_url,
            api_key=self.api_key,
            workspace_slug=self.workspace_slug
        )


def _safe_llm_client() -> Optional[LLMClient]:
    """Create LLM client if API key is configured; otherwise return None."""
    has_key = os.getenv("API_KEY") or os.getenv("OPENAI_API_KEY")
    if not has_key:
        logger.warning("LLM API key is missing; falling back to rule-based extraction.")
        return None
    try:
        return LLMClient()
    except Exception as exc:
        logger.warning("Failed to initialize LLM client, will use rule-based only: %s", exc)
        return None


@lru_cache()
def get_plane_factory() -> PlaneAPIFactory:
    """Get or create PlaneAPIFactory instance."""
    return PlaneAPIFactory()


@lru_cache()
def get_work_report_extractor() -> WorkReportExtractor:
    """Get or create the work report extractor service."""
    llm_client = LLMClient()
    return WorkReportExtractor(llm_client)


@lru_cache()
def get_chat_service() -> ChatService:
    """
    Get or create the ChatService instance.
    
    This function uses dependency injection to wire up all the services.
    The @lru_cache decorator ensures we only create one instance.
    """
    # Initialize infrastructure components
    llm_client = LLMClient()
    redis_memory = RedisMemory()
    router = Router(llm_client)
    general_bot = GeneralBot(llm_client)
    plane_factory = PlaneAPIFactory()
    
    # Wrap Redis memory to implement MemoryInterface
    class MemoryWrapper:
        def __init__(self, redis_mem):
            self.redis = redis_mem
        
        def add_message(self, user_id, role, content):
            self.redis.add_message(user_id, role, content)
        
        def get_history(self, user_id, limit=None):
            from auto_pm_agent_api.domain.memory import ConversationHistory
            history = self.redis.get_history(user_id)
            if limit:
                history = history[-limit:]
            return ConversationHistory.from_list(user_id, history)
        
        def clear_history(self, user_id):
            self.redis.clear_history(user_id)
    
    memory = MemoryWrapper(redis_memory)
    
    # Initialize application services
    project_service = ProjectManagementService(llm_client, plane_factory)
    qa_service = QAService(llm_client, plane_factory)
    assignment_service = AssignmentService(llm_client, plane_factory)
    
    # Report session manager
    report_manager = ReportSessionManager(general_bot, plane_factory)

    # Create and return chat service
    return ChatService(
        memory=memory,
        intent_classifier=router,
        project_service=project_service,
        qa_service=qa_service,
        assignment_service=assignment_service,
        general_bot=general_bot,
        report_manager=report_manager,
    )
