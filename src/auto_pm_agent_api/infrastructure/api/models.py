"""API request and response models."""

from pydantic import BaseModel, Field
from typing import Optional

from auto_pm_agent_api.domain.models import WorkReportData


class ChatRequest(BaseModel):
    """Request model for chat endpoint."""
    
    user_id: int = Field(..., description="Unique user identifier")
    role: str = Field("manager", description="User role: manager | staff")
    query: Optional[str] = Field(None, description="User query text")
    file_content: Optional[str] = Field(None, description="File content for project creation")
    long_memory: Optional[str] = Field(None, description="Optional long-term memory context")
    mode_report: bool = Field(False, description="Whether the user is in report mode")

    class Config:
        schema_extra = {
            "example": {
                "user_id": 123,
                "role": "manager",
                "query": "Tạo project mới từ file này",
                "file_content": None,
                "long_memory": None,
                "mode_report": False
            }
        }


class ChatResponse(BaseModel):
    """Response model for chat endpoint."""
    
    user_id: int = Field(..., description="User identifier")
    query: Optional[str] = Field(None, description="Original user query")
    response: str = Field(..., description="Chatbot response")
    success: bool = Field(True, description="Whether the request was successful")
    error: Optional[str] = Field(None, description="Error message if any")
    mode_report: bool = Field(False, description="Current report mode flag")

    class Config:
        schema_extra = {
            "example": {
                "user_id": 123,
                "query": "Tạo project mới",
                "response": "Tôi đã tạo project thành công!",
                "success": True,
                "error": None,
                "mode_report": False
            }
        }


class WorkReportExtractRequest(BaseModel):
    """Request model for extracting work report content."""

    content: str = Field(..., description="Nội dung báo cáo công việc dạng text")

    class Config:
        schema_extra = {
            "example": {
                "content": "1. Today work: ... 2. Issues: ... 3. Tomorrow plan: ..."
            }
        }


class WorkReportExtractResponse(BaseModel):
    """Response model for work report extraction."""

    success: bool = Field(True, description="Whether the extraction succeeded")
    data: Optional[WorkReportData] = Field(None, description="Báo cáo đã được trích xuất")
    message: str = Field(..., description="Thông báo kết quả")
    error: Optional[str] = Field(None, description="Chi tiết lỗi (nếu có)")

    class Config:
        schema_extra = {
        "example": {
            "success": True,
            "message": "Trích xuất báo cáo thành công",
            "data": {
                "daily_tasks": {
                    "tasks": [
                        {
                            "id": "TMNDKM",
                            "title": "Test module nhận diện khuôn mặt",
                            "status": "in_progress",
                            "progress": 80,
                            "time_spent": "4h"
                        }
                    ],
                    "blockers": [],
                    "achievements": []
                },
                "notes": "Báo cáo công việc ngày hôm nay:\\n\\nHôm nay tôi đã làm việc ...",
                "created_by": None,
                "updated_by": None,
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z"
            },
            "error": None
        }
    }
