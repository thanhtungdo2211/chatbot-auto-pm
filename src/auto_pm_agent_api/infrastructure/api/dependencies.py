"""Dependency injection for API endpoints."""

import os
from functools import lru_cache
from dotenv import load_dotenv
from typing import Optional

from auto_pm_agent_api.application.chat_service import ChatService
from auto_pm_agent_api.application.project_management_service import ProjectManagementService
from auto_pm_agent_api.application.qa_service import QAService
from auto_pm_agent_api.application.assignment_service import AssignmentService

from auto_pm_agent_api.infrastructure.llm_providers import LLMClient
from auto_pm_agent_api.infrastructure.db import RedisMemory, MemorySelectBot
from auto_pm_agent_api.infrastructure.llm_providers import Router, GeneralBot
from auto_pm_agent_api.infrastructure.plane_client import PlaneAPIClient

# Load environment variables
load_dotenv()


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

@lru_cache()
def get_plane_factory() -> PlaneAPIFactory:
    """Get or create PlaneAPIFactory instance."""
    return PlaneAPIFactory()

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
    memory_select_bot = MemorySelectBot(llm_client)
    router = Router(llm_client)
    general_bot = GeneralBot(llm_client)
    plane_factory = PlaneAPIFactory()
    
    # Wrap Redis memory with selector
    class MemoryWithSelector:
        def __init__(self, redis_mem, selector):
            self.redis = redis_mem
            self.selector = selector
        
        def add_message(self, user_id, role, content):
            self.redis.add_message(user_id, role, content)
        
        def get_history(self, user_id, limit=None):
            from auto_pm_agent_api.domain.memory import ConversationHistory
            history = self.redis.get_history(user_id)
            return ConversationHistory.from_list(user_id, history)
        
        def clear_history(self, user_id):
            self.redis.clear_history(user_id)
        
        def select_relevant_history(self, user_id, query, max_messages=5):
            from auto_pm_agent_api.domain.memory import ConversationHistory
            history = self.redis.get_history(user_id)
            if not history:
                return ConversationHistory(user_id=user_id, messages=[])
            
            selected = self.selector.get_memory_select(history, query)
            return ConversationHistory.from_list(user_id, selected)
    
    memory = MemoryWithSelector(redis_memory, memory_select_bot)
    
    # Initialize application services
    project_service = ProjectManagementService(llm_client, plane_factory)
    qa_service = QAService(llm_client, plane_factory)
    assignment_service = AssignmentService(llm_client, plane_factory)
    
    # Create and return chat service
    return ChatService(
        memory=memory,
        intent_classifier=router,
        project_service=project_service,
        qa_service=qa_service,
        assignment_service=assignment_service,
        general_bot=general_bot
    )
