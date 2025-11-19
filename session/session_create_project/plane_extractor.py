from pydantic import BaseModel, Field, validator, ValidationError
from typing import List, Optional
import sys
from pathlib import Path
import re
import json

from .prompt.prompt_plane_extractor import PROMPT_PLANE_EXTRACT


# -----------------------------
# Định nghĩa Schema
# -----------------------------
class TaskSchema(BaseModel):
    name: str = Field(..., description="Tên công việc (task name)")
    description: Optional[str] = Field(None, description="Mô tả hoặc kết quả task")
    start_date: Optional[str] = Field(None, description="Ngày bắt đầu (YYYY-MM-DD)")
    target_date: Optional[str] = Field(None, description="Ngày kết thúc (YYYY-MM-DD)")


class ProjectSchema(BaseModel):
    name: str = Field(..., description="Tên dự án")
    identifier: str = Field(..., description="Mã viết tắt cho dự án (4-6 ký tự in hoa, không dấu)")
    description: Optional[str] = Field(None, description="Mô tả ngắn gọn về dự án")



class ExtractedPlaneData(BaseModel):
    is_info_project: bool = Field(..., description="True nếu nội dung là thông tin dự án, False nếu không")
    project: Optional[ProjectSchema] = None
    tasks: Optional[List[TaskSchema]] = None


# -----------------------------
# Lớp chính dùng LLM
# -----------------------------
class PlaneExtractor:
    def __init__(self, llm_client):
        self.llm = llm_client
        
    def extract(self, data: str):
        """
        Trích xuất thông tin project + task từ dữ liệu JSON gốc.
        """
        prompt = PROMPT_PLANE_EXTRACT +  data
        result = self.llm.generate_response(prompt, ExtractedPlaneData)
        # Nếu trả về list thì lấy phần tử đầu tiên
        if isinstance(result, list) and len(result) > 0:
            result = result[0]
        return result



