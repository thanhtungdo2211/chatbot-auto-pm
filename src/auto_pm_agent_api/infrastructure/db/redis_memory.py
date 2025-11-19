"""Redis-based memory implementation."""

import redis
import json
import os
from typing import List, Optional
from dotenv import load_dotenv

load_dotenv()


class RedisMemory:
    """
    Redis-based conversation memory storage.
    
    Stores recent conversation history in Redis with automatic trimming.
    """

    def __init__(
        self,
        redis_host: str = None,
        redis_port: int = None,
        redis_db: int = 0
    ):
        """
        Initialize Redis memory.
        
        Args:
            redis_host: Redis server host (defaults to env variable or localhost)
            redis_port: Redis server port (defaults to env variable or 6379)
            redis_db: Redis database number
        """
        self.redis_host = redis_host or os.getenv("REDIS_HOST", "localhost")
        self.redis_port = redis_port or int(os.getenv("REDIS_PORT", "6379"))
        self.redis_db = redis_db
        
        self.redis = redis.Redis(
            host=self.redis_host,
            port=self.redis_port,
            db=self.redis_db,
            decode_responses=True
        )
        self.max_messages = 10  # Keep only the 10 most recent messages

    def _get_redis_key(self, user_id: int) -> str:
        """Generate Redis key for a user."""
        return f"chat_history:{user_id}"

    def add_message(self, user_id: int, role: str, content: str) -> None:
        """
        Add a message to the conversation history.
        
        Args:
            user_id: User identifier
            role: Message role (user/chatbot)
            content: Message content
        """
        key = self._get_redis_key(user_id)
        msg = json.dumps({"role": role, "content": content})
        self.redis.rpush(key, msg)
        self.redis.ltrim(key, -self.max_messages, -1)

    def get_history(self, user_id: int) -> List[dict]:
        """
        Retrieve conversation history for a user.
        
        Args:
            user_id: User identifier
            
        Returns:
            List of message dictionaries
        """
        key = self._get_redis_key(user_id)
        history = self.redis.lrange(key, 0, -1)
        
        if not history:
            return []
        
        return [json.loads(m) for m in history]

    def clear_history(self, user_id: int) -> None:
        """
        Clear conversation history for a user.
        
        Args:
            user_id: User identifier
        """
        key = self._get_redis_key(user_id)
        self.redis.delete(key)
