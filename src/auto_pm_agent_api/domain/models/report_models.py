"""Pydantic models for work report extraction."""

from typing import List, Optional
from pydantic import BaseModel, Field


class DailyTask(BaseModel):
    """Thông tin chi tiết về một task trong ngày."""

    id: Optional[str] = Field(
        None, description="Mã hoặc viết tắt của task (nếu không có có thể tự sinh)"
    )
    title: str = Field("", description="Tên task")
    status: str = Field("todo", description="Trạng thái: todo, in_progress, done")
    progress: int = Field(0, description="Tiến độ hoàn thành (%)")
    time_spent: Optional[str] = Field(
        None, description="Thời gian đã làm, ví dụ: 4h, 2.5h, 45m"
    )


class DailyTasks(BaseModel):
    """Tổng hợp task, blocker và achievement trong ngày."""

    tasks: List[DailyTask] = Field(default_factory=list, description="Danh sách task")
    blockers: List[str] = Field(default_factory=list, description="Các blocker")
    achievements: List[str] = Field(default_factory=list, description="Các thành tựu nổi bật")


class WorkReportData(BaseModel):
    """Normalized work report data."""

    daily_tasks: DailyTasks = Field(default_factory=DailyTasks, description="Báo cáo task hằng ngày")
    notes: str = Field("", description="Toàn bộ ghi chú/tóm tắt báo cáo gốc")
    created_by: Optional[str] = Field(None, description="Người tạo báo cáo")
    updated_by: Optional[str] = Field(None, description="Người cập nhật báo cáo")
    created_at: Optional[str] = Field(
        None, description="Thời gian tạo báo cáo theo ISO 8601, UTC"
    )
    updated_at: Optional[str] = Field(
        None, description="Thời gian cập nhật báo cáo theo ISO 8601, UTC"
    )
