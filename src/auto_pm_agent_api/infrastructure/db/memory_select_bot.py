"""Memory selection bot for filtering relevant conversation history."""

from typing import List
from auto_pm_agent_api.domain.prompts import PROMPT_MEMORY_SELECT
from auto_pm_agent_api.infrastructure.llm_providers.llm_client import LLMClient


class MemorySelectBot:
    """
    Bot for selecting relevant messages from conversation history.
    
    Uses LLM to intelligently filter conversation history based on
    the current query, keeping only the most relevant context.
    """

    def __init__(self, llm_client: LLMClient = None):
        """
        Initialize memory selector.
        
        Args:
            llm_client: Optional LLM client instance
        """
        self.llm = llm_client or LLMClient()

    def get_memory_select(
        self,
        history: List[dict],
        query: str,
        max_messages: int = 5
    ) -> List[dict]:
        """
        Select relevant messages from history based on query.
        
        Args:
            history: Full conversation history
            query: Current user query
            max_messages: Maximum messages to return
            
        Returns:
            List of relevant message dictionaries
        """
        if not history:
            return []
        
        if len(history) <= max_messages:
            return history
        
        # For now, return the most recent messages
        # TODO: Implement LLM-based selection
        return history[-max_messages:]
