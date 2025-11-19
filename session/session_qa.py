from pydantic import BaseModel, Field
from typing import Optional, List
import sys
from pathlib import Path

# Add parent directory to path
FILE = Path(__file__).resolve()
ROOT = FILE.parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from session.session_create_project.update_plane import PlaneAPI

# -----------------------------
# Prompt cho QA với RAG
# -----------------------------
PROMPT_QA_RAG = """
Bạn là một trợ lý AI thông minh, có nhiệm vụ trả lời các câu hỏi về dự án dựa trên dữ liệu được cung cấp.

🎯 Nhiệm vụ:
Dựa vào dữ liệu về projects, tasks và members bên dưới, hãy trả lời câu hỏi của người dùng một cách chính xác và đầy đủ.

📋 Dữ liệu hiện có:
{context}

❓ Câu hỏi của người dùng:
{query}

📝 Lịch sử hội thoại:
{history}

⚙️ Quy tắc:
1. Chỉ trả lời dựa trên dữ liệu được cung cấp
2. Nếu không tìm thấy thông tin, hãy nói rõ là không có dữ liệu
3. Trả lời bằng tiếng Việt, rõ ràng và dễ hiểu
4. Nếu có nhiều kết quả, liệt kê đầy đủ
5. Đưa ra số liệu cụ thể khi được hỏi về số lượng
6. Không trả về thông tin ID trên hệ thống Plane. 
Hãy trả lời câu hỏi:
"""

# -----------------------------
# Schema cho output
# -----------------------------
class QAResponse(BaseModel):
    answer: str = Field(..., description="Câu trả lời cho câu hỏi của người dùng")
    found_data: bool = Field(..., description="True nếu tìm thấy dữ liệu liên quan")
    related_items: Optional[List[str]] = Field(None, description="Danh sách các items liên quan")

# -----------------------------
# Session QA chính
# -----------------------------
class SessionQA:
    def __init__(self, llm_client):
        self.llm = llm_client
        self.api_key_plane = None
        self.workspace_slug = None
        self.plane_api = None
        self.cached_data = None

    def get_info_plane(self, user_id):
        self.api_key_plane = "plane_api_d958d52c6c0845cb94b8dadd7fef425e"
        self.workspace_slug = "thang"
        self.plane_api = PlaneAPI(self.api_key_plane, self.workspace_slug)

    # -------------------------------------
    # Lấy full data từ Plane (safe normalize)
    # -------------------------------------
    def refresh_data(self):
        if self.plane_api is None:
            return []

        data = self.plane_api.get_all_data_for_rag()
        if not data:
            return []

        # Ép tất cả phải là dict
        data = [d for d in data if isinstance(d, dict)]

        self.cached_data = data
        return data

    # -------------------------------------
    # Format context cho LLM
    # -------------------------------------
    def format_context(self, data):
        if not data:
            return "Không có dữ liệu"

        projects = [d for d in data if d["type"] == "project"]
        issues   = [d for d in data if d["type"] == "issue"]
        members  = [d for d in data if d["type"] == "member"]
        members_workspace = [d for d in data if d["type"] == "workspace_member"]
        ctx = []

        if projects:
            ctx.append("=== PROJECTS ===")
            for p in projects:
                ctx.append(f"- {p['name']} | ID: {p['id']}")
                if p.get("description"):
                    ctx.append(f"  Mô tả: {p['description']}")

        if issues:
            ctx.append("\n=== TASKS ===")
            for t in issues:
                ctx.append(f"- {t['name']} (Project: {t['project_name']})")
                ctx.append(f"- Priority: {t.get('priority', 'None')}")
                ctx.append(f"  Thời gian: {t.get('start_date')} -> {t.get('target_date')}")
                if t.get("assignees"):
                    ctx.append(f"  Assignees: {t['assignees']}")

        if members:
            ctx.append("\n=== MEMBERS ===")
            for m in members:
                ctx.append(f"- {m['name']} (Project: {m['project_name']})")
                ctx.append(f"  Email: {m.get('email')}, Role: {m.get('role')}")
        if members_workspace:
            ctx.append("\n=== WORKSPACE MEMBERS INFO ===")
            for m in members_workspace:
                ctx.append(f"- {m['name']} (Workspace)")
                ctx.append(f"  Email: {m.get('email')}, Role: {m.get('role')}")
        return "\n".join(ctx)

    # -------------------------------------
    # Handle QA session
    # -------------------------------------
    def handle_session(self, user_id, query):
        if self.plane_api is None:
            self.get_info_plane(user_id)

        data = self.refresh_data()
        if not data:
            return None, "Không thể lấy dữ liệu từ Plane API."

        context = self.format_context(data)

        prompt = PROMPT_QA_RAG.format(
            context=context,
            query=query,
            history="Không có lịch sử"
        )

        response = self.llm.generate_response(prompt)
        return None, response



# -----------------------------
# Test
# -----------------------------
if __name__ == "__main__":
    from llm.llm_client import LLMClient

    llm = LLMClient()
    session = SessionQA(llm)

    # Test query
    test_queries = [
        "Có bao nhiêu project trong hệ thống?",
        "Liệt kê các task chưa hoàn thành",
        "Ai đang làm việc trong project AI2School?"
    ]

    for q in test_queries:
        session_state, response = session.handle_session("test_user", q)
        print(f"Q: {q}")
        print(f"A: {response}")
        print("-" * 50)
