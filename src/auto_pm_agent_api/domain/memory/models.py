"""Domain models for memory."""

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional


@dataclass
class ChatMessage:
    """Represents a single chat message."""
    
    role: str  # "user" or "chatbot"
    content: str
    timestamp: Optional[datetime] = None

    def to_dict(self) -> dict:
        """Convert to dictionary format."""
        result = {"role": self.role, "content": self.content}
        if self.timestamp:
            result["timestamp"] = self.timestamp.isoformat()
        return result

    @classmethod
    def from_dict(cls, data: dict) -> "ChatMessage":
        """Create from dictionary format."""
        timestamp = None
        if "timestamp" in data:
            timestamp = datetime.fromisoformat(data["timestamp"])
        return cls(
            role=data["role"],
            content=data["content"],
            timestamp=timestamp
        )


@dataclass
class ConversationHistory:
    """Represents a conversation history."""
    
    user_id: int
    messages: List[ChatMessage]

    def to_list(self) -> List[dict]:
        """Convert messages to list of dictionaries."""
        return [msg.to_dict() for msg in self.messages]

    def to_string(self) -> str:
        """Convert to formatted string for LLM context."""
        if not self.messages:
            return "No previous conversation."
        
        lines = []
        for msg in self.messages:
            role_label = "User" if msg.role == "user" else "Chatbot"
            lines.append(f"{role_label}: {msg.content}")
        return "\n".join(lines)

    @classmethod
    def from_list(cls, user_id: int, messages: List[dict]) -> "ConversationHistory":
        """Create from list of message dictionaries."""
        chat_messages = [ChatMessage.from_dict(msg) for msg in messages]
        return cls(user_id=user_id, messages=chat_messages)
