"""Router for intent classification using LLM."""

from auto_pm_agent_api.domain.tools import IntentClassifier, IntentResult
from auto_pm_agent_api.domain.prompts import PROMPT_ROUTER
from auto_pm_agent_api.infrastructure.llm_providers.llm_client import LLMClient


class Router(IntentClassifier):
    """
    LLM-based router for classifying user intents.
    
    Implements the IntentClassifier interface from the domain layer.
    """

    def __init__(self, llm_client: LLMClient = None):
        """
        Initialize router.
        
        Args:
            llm_client: Optional LLM client instance
        """
        self.llm = llm_client or LLMClient()

    def classify(self, history: str, query: str) -> IntentResult:
        """
        Classify user intent based on conversation history and current query.
        
        Args:
            history: Formatted conversation history
            query: Current user query
            
        Returns:
            IntentResult with classified intent
        """
        prompt = PROMPT_ROUTER.format(
            selected_history=history or "No previous conversation.",
            query=query
        )

        result = self.llm.generate_response(prompt, IntentResult)
        
        return result
