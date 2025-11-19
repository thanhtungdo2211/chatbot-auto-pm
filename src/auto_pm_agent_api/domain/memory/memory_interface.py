"""Memory interface and models for the domain layer."""

from abc import ABC, abstractmethod
from typing import List, Optional
from auto_pm_agent_api.domain.memory.models import ChatMessage, ConversationHistory


class MemoryInterface(ABC):
    """Abstract interface for memory operations."""

    @abstractmethod
    def add_message(self, user_id: int, role: str, content: str) -> None:
        """Add a message to the conversation history.
        
        Args:
            user_id: User identifier
            role: Message role (user/chatbot)
            content: Message content
        """
        pass

    @abstractmethod
    def get_history(self, user_id: int, limit: Optional[int] = None) -> ConversationHistory:
        """Retrieve conversation history for a user.
        
        Args:
            user_id: User identifier
            limit: Maximum number of messages to retrieve
            
        Returns:
            ConversationHistory object
        """
        pass

    @abstractmethod
    def clear_history(self, user_id: int) -> None:
        """Clear conversation history for a user.
        
        Args:
            user_id: User identifier
        """
        pass

    @abstractmethod
    def select_relevant_history(
        self, user_id: int, query: str, max_messages: int = 5
    ) -> ConversationHistory:
        """Select relevant messages from history based on query.
        
        Args:
            user_id: User identifier
            query: Current user query
            max_messages: Maximum messages to return
            
        Returns:
            ConversationHistory with relevant messages
        """
        pass
