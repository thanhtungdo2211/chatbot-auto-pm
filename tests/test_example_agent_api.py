"""Example tests for the Awesome Agent API."""

import pytest
from auto_pm_agent_api.domain.memory import ChatMessage, ConversationHistory
from auto_pm_agent_api.utils import (
    normalize_string,
    is_affirmative,
    truncate_text,
    chunk_list
)


class TestChatMessage:
    """Tests for ChatMessage domain model."""
    
    def test_chat_message_creation(self):
        """Test creating a chat message."""
        msg = ChatMessage(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"
    
    def test_chat_message_to_dict(self):
        """Test converting chat message to dictionary."""
        msg = ChatMessage(role="chatbot", content="Hi there")
        d = msg.to_dict()
        assert d["role"] == "chatbot"
        assert d["content"] == "Hi there"
    
    def test_chat_message_from_dict(self):
        """Test creating chat message from dictionary."""
        data = {"role": "user", "content": "Test"}
        msg = ChatMessage.from_dict(data)
        assert msg.role == "user"
        assert msg.content == "Test"


class TestConversationHistory:
    """Tests for ConversationHistory domain model."""
    
    def test_conversation_history_creation(self):
        """Test creating conversation history."""
        messages = [
            ChatMessage(role="user", content="Hello"),
            ChatMessage(role="chatbot", content="Hi"),
        ]
        history = ConversationHistory(user_id=1, messages=messages)
        assert history.user_id == 1
        assert len(history.messages) == 2
    
    def test_to_list(self):
        """Test converting history to list."""
        messages = [ChatMessage(role="user", content="Test")]
        history = ConversationHistory(user_id=1, messages=messages)
        lst = history.to_list()
        assert isinstance(lst, list)
        assert len(lst) == 1
        assert lst[0]["role"] == "user"
    
    def test_to_string(self):
        """Test converting history to string."""
        messages = [
            ChatMessage(role="user", content="Hello"),
            ChatMessage(role="chatbot", content="Hi there"),
        ]
        history = ConversationHistory(user_id=1, messages=messages)
        s = history.to_string()
        assert "User: Hello" in s
        assert "Chatbot: Hi there" in s


class TestUtils:
    """Tests for utility functions."""
    
    def test_normalize_string(self):
        """Test string normalization."""
        assert normalize_string("  Hello   World  ") == "hello world"
        assert normalize_string("TEST") == "test"
    
    def test_is_affirmative(self):
        """Test affirmative detection."""
        assert is_affirmative("Có") == True
        assert is_affirmative("yes") == True
        assert is_affirmative("ok") == True
        assert is_affirmative("no") == False
        assert is_affirmative("không") == False
    
    def test_truncate_text(self):
        """Test text truncation."""
        text = "This is a very long text that needs to be truncated"
        result = truncate_text(text, max_length=20)
        assert len(result) <= 20
        assert result.endswith("...")
    
    def test_chunk_list(self):
        """Test list chunking."""
        lst = [1, 2, 3, 4, 5, 6, 7, 8, 9]
        chunks = chunk_list(lst, chunk_size=3)
        assert len(chunks) == 3
        assert chunks[0] == [1, 2, 3]
        assert chunks[2] == [7, 8, 9]


class TestAPI:
    """Tests for API endpoints."""
    
    def test_root_endpoint(self):
        """Test root endpoint returns success."""
        # This would use TestClient from FastAPI
        # from fastapi.testclient import TestClient
        # from auto_pm_agent_api.infrastructure.api.main import app
        # client = TestClient(app)
        # response = client.get("/")
        # assert response.status_code == 200
        pass
    
    def test_health_endpoint(self):
        """Test health check endpoint."""
        pass
    
    def test_chat_endpoint(self):
        """Test chat endpoint with valid request."""
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
