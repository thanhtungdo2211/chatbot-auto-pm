"""API request and response models."""

from pydantic import BaseModel, Field
from typing import Optional


class ChatRequest(BaseModel):
    """Request model for chat endpoint."""
    
    user_id: int = Field(..., description="Unique user identifier")
    query: Optional[str] = Field(None, description="User query text")
    file_content: Optional[str] = Field(None, description="File content for project creation")
    long_memory: Optional[str] = Field(None, description="Optional long-term memory context")

    class Config:
        schema_extra = {
            "example": {
                "user_id": 123,
                "query": "Tạo project mới từ file này",
                "file_content": None,
                "long_memory": None
            }
        }


class ChatResponse(BaseModel):
    """Response model for chat endpoint."""
    
    user_id: int = Field(..., description="User identifier")
    query: Optional[str] = Field(None, description="Original user query")
    response: str = Field(..., description="Chatbot response")
    success: bool = Field(True, description="Whether the request was successful")
    error: Optional[str] = Field(None, description="Error message if any")

    class Config:
        schema_extra = {
            "example": {
                "user_id": 123,
                "query": "Tạo project mới",
                "response": "Tôi đã tạo project thành công!",
                "success": True,
                "error": None
            }
        }
