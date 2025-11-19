"""Test configuration and fixtures."""

import pytest
from unittest.mock import Mock

from auto_pm_agent_api.infrastructure.llm_providers import LLMClient
from auto_pm_agent_api.infrastructure.db import RedisMemory
from auto_pm_agent_api.domain.memory import ConversationHistory, ChatMessage


@pytest.fixture
def mock_llm_client():
    """Mock LLM client for testing."""
    client = Mock(spec=LLMClient)
    client.generate_response.return_value = "Mock response"
    return client


@pytest.fixture
def mock_redis_memory():
    """Mock Redis memory for testing."""
    memory = Mock(spec=RedisMemory)
    memory.get_history.return_value = []
    return memory


@pytest.fixture
def sample_conversation_history():
    """Sample conversation history for testing."""
    messages = [
        ChatMessage(role="user", content="Hello"),
        ChatMessage(role="chatbot", content="Hi there!"),
        ChatMessage(role="user", content="How are you?"),
        ChatMessage(role="chatbot", content="I'm doing well, thank you!"),
    ]
    return ConversationHistory(user_id=123, messages=messages)


@pytest.fixture
def sample_chat_request():
    """Sample chat request data."""
    return {
        "user_id": 123,
        "query": "Create a new project",
        "file_content": None,
        "long_memory": None
    }
