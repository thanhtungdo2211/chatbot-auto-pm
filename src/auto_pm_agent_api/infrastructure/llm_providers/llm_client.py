"""LLM client for interacting with language models."""

import os
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from typing import Optional, Type
from pydantic import BaseModel

load_dotenv()


class LLMClient:
    """
    Client for interacting with LLM providers.
    
    Supports structured output and general text generation.
    """

    def __init__(self):
        """Initialize LLM client with configuration from environment."""
        self.model_name = os.getenv("MODEL_NAME", "gpt-3.5-turbo")
        self.base_url = os.getenv("BASE_URL", "https://openrouter.ai/api/v1")
        self.api_key = os.getenv("API_KEY", os.getenv("OPENAI_API_KEY"))
        
        # Detect if using OpenRouter
        is_openrouter = self.api_key and self.api_key.startswith("sk-or-")
        
        if is_openrouter:
            # For OpenRouter, set as OPENAI_API_KEY and use their base URL
            os.environ["OPENAI_API_KEY"] = self.api_key
            if not self.base_url or self.base_url == "https://api.openai.com/v1":
                self.base_url = "https://openrouter.ai/api/v1"
            
            # Initialize with OpenRouter settings
            self.llm = init_chat_model(
                model=self.model_name,
                model_provider="openai",  # OpenRouter uses OpenAI-compatible API
                base_url=self.base_url,
                openai_api_key=self.api_key
            )
        else:
            # Standard OpenAI setup
            if self.api_key:
                os.environ["OPENAI_API_KEY"] = self.api_key
            
            self.llm = init_chat_model(
                model=self.model_name,
                model_provider="openai",
                base_url=self.base_url,
                openai_api_key=self.api_key
            )

        self.llm_structured = None

    def generate_response(
        self,
        prompt: str,
        output_format: Optional[Type[BaseModel]] = None
    ):
        """
        Generate a response from the LLM.
        
        Args:
            prompt: The input prompt
            output_format: Optional Pydantic model for structured output
            
        Returns:
            Generated response (string or structured object)
        """
        if output_format is not None:
            self.llm_structured = self.llm.with_structured_output(output_format)
            return self.llm_structured.invoke(prompt)
        else:
            result = self.llm.invoke(prompt)
            return result.content if hasattr(result, 'content') else str(result)