"""Intent classification for routing user queries."""

from pydantic import BaseModel, Field
from typing import Literal
from abc import ABC, abstractmethod


class IntentResult(BaseModel):
    """Result of intent classification."""
    
    intent: Literal[
        "create_new_project",
        "update_existing_information",
        "ask_about_existing_information",
        "update_plane_information",
        "assignment",
        "other_topics",
    ] = Field(..., description="Intent classification label")


class IntentClassifier(ABC):
    """Abstract interface for intent classification."""

    @abstractmethod
    def classify(self, history: str, query: str) -> IntentResult:
        """Classify user intent based on conversation history and current query.
        
        Args:
            history: Formatted conversation history
            query: Current user query
            
        Returns:
            IntentResult with classified intent
        """
        pass
