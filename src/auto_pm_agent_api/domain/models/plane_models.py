"""Pydantic models for Plane project extraction."""

from pydantic import BaseModel, Field
from typing import List, Optional


class TaskSchema(BaseModel):
    """Schema for a task/issue in a project."""
    
    name: str = Field(..., description="Tên công việc (task name)")
    description: Optional[str] = Field(None, description="Mô tả hoặc kết quả task")
    start_date: Optional[str] = Field(None, description="Ngày bắt đầu (YYYY-MM-DD)")
    target_date: Optional[str] = Field(None, description="Ngày kết thúc (YYYY-MM-DD)")


class ProjectSchema(BaseModel):
    """Schema for a project."""
    
    name: str = Field(..., description="Tên dự án")
    identifier: str = Field(..., description="Mã viết tắt cho dự án (4-6 ký tự in hoa, không dấu)")
    description: Optional[str] = Field(None, description="Mô tả ngắn gọn về dự án")


class ExtractedPlaneData(BaseModel):
    """Schema for extracted project data from file content."""
    
    is_info_project: bool = Field(..., description="True nếu nội dung là thông tin dự án, False nếu không")
    project: Optional[ProjectSchema] = None
    tasks: Optional[List[TaskSchema]] = None
