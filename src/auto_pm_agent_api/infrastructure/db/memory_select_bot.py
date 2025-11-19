"""Memory selection bot for filtering relevant conversation history."""

import json
import logging
from typing import List
from auto_pm_agent_api.domain.prompts import PROMPT_MEMORY_SELECT
from auto_pm_agent_api.infrastructure.llm_providers.llm_client import LLMClient

logger = logging.getLogger(__name__)


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
        Select relevant messages from history based on query using LLM.
        
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
        
        try:
            # Format history for prompt
            history_str = json.dumps(history, ensure_ascii=False, indent=2)
            
            # Build prompt
            prompt = PROMPT_MEMORY_SELECT.format(
                full_history=history_str,
                query=query,
                max_messages=max_messages
            )
            
            # Get LLM response
            response = self.llm.generate_response(prompt)
            logger.info(f"Memory selection LLM response: {response[:200]}...")
            
            # Parse JSON response
            try:
                selected = json.loads(response)
                if isinstance(selected, list):
                    logger.info(f"Selected {len(selected)} messages from {len(history)} total")
                    return selected
                else:
                    logger.warning("LLM returned non-list response, using recent messages")
                    return history[-max_messages:]
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse LLM response as JSON: {e}")
                logger.debug(f"Raw response: {response}")
                # Fallback to recent messages
                return history[-max_messages:]
                
        except Exception as e:
            logger.error(f"Error in memory selection: {e}", exc_info=True)
            # Fallback to recent messages
            return history[-max_messages:]
