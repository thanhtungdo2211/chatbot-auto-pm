"""General chatbot for handling non-work-related queries."""

from auto_pm_agent_api.domain.prompts import PROMPT_GENERAL_BOT
from auto_pm_agent_api.infrastructure.llm_providers.llm_client import LLMClient


class GeneralBot:
    """
    General purpose chatbot for handling queries outside the main domain.
    
    Handles casual conversation and redirects to work topics when appropriate.
    """

    def __init__(self, llm_client: LLMClient = None):
        """
        Initialize general bot.
        
        Args:
            llm_client: Optional LLM client instance
        """
        self.llm = llm_client or LLMClient()

    def generate_response(self, history: str, query: str) -> str:
        """
        Generate a response for general queries.
        
        Args:
            history: Formatted conversation history
            query: Current user query
            
        Returns:
            Response string
        """
        prompt = PROMPT_GENERAL_BOT.format(
            selected_history=history or "No previous conversation.",
            query=query
        )
        
        return self.llm.generate_response(prompt)
