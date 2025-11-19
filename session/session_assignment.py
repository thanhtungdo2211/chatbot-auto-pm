from pydantic import BaseModel, Field
from typing import Optional, List
import json
import sys
from pathlib import Path

# Add parent directory to path
FILE = Path(__file__).resolve()
ROOT = FILE.parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from session.session_create_project.update_plane import PlaneAPI
from session.session_create_project.check import AffirmativeChecker

# -----------------------------
# Prompt để phân tích và gợi ý phân công
# -----------------------------
PROMPT_ASSIGNMENT = """
Bạn là một trợ lý AI thông minh, có nhiệm vụ gợi ý phân công task cho các thành viên một cách tối ưu.

🎯 Nhiệm vụ:
Dựa vào danh sách tasks cần giao và thông tin về members (bao gồm workload hiện tại), hãy đề xuất phân công tối ưu.

📋 Danh sách Tasks cần giao:
{tasks}

👥 Danh sách Members và Workload hiện tại:
{members}

⚙️ Tiêu chí phân công:
1. Cân bằng workload giữa các thành viên
2. Ưu tiên người có ít task hơn
3. Xem xét độ ưu tiên của task (urgent/high trước)
4. Phân bổ đều đặn, không để một người quá tải

📝 Yêu cầu output:
Trả về danh sách phân công với lý do cụ thể cho mỗi assignment.
"""

# -----------------------------
# Schema cho assignment
# -----------------------------
class AssignmentItem(BaseModel):
    task_id: str = Field(..., description="ID của task")
    task_name: str = Field(..., description="Tên task")
    member_id: str = Field(..., description="ID của member được giao")
    member_name: str = Field(..., description="Tên member được giao")
    reason: str = Field(..., description="Lý do phân công")

class AssignmentResult(BaseModel):
    assignments: List[AssignmentItem] = Field(..., description="Danh sách phân công")
    summary: str = Field(..., description="Tóm tắt phân công")

# -----------------------------
# Schema để extract yêu cầu assignment
# -----------------------------
class AssignmentRequest(BaseModel):
    project_name: Optional[str] = Field(None, description="Tên dự án")
    task_count: Optional[int] = Field(None, description="Số lượng task cần giao")
    specific_tasks: Optional[List[str]] = Field(None, description="Danh sách tên task cụ thể")
    assign_unassigned: bool = Field(True, description="Giao các task chưa có assignee")

PROMPT_EXTRACT_ASSIGNMENT = """
Bạn là một trợ lý AI, có nhiệm vụ trích xuất yêu cầu phân công task từ tin nhắn của người dùng.

❓ Yêu cầu của người dùng:
{query}

📝 Lịch sử hội thoại:
{history}

🎯 Trích xuất:
- project_name: Tên dự án (nếu có đề cập)
- task_count: Số lượng task muốn giao (nếu có)
- specific_tasks: Danh sách tên task cụ thể (nếu có)
- assign_unassigned: True nếu muốn giao các task chưa có người làm

Trả về JSON theo schema.
"""

# -----------------------------
# Session Assignment chính
# -----------------------------
class SessionAssignment:
    def __init__(self, llm_client):
        self.llm = llm_client
        self.api_key_plane = None
        self.workspace_slug = None
        self.plane_api = None
        self.affirmative_checker = AffirmativeChecker(llm_client)

        # Session state
        self.status = None
        self.pending_assignments = []
        self.project_id = None

    def get_info_plane(self, user_id):
        """Lấy thông tin Plane API từ user config"""
        self.api_key_plane = "plane_api_49e5f398343f4a13a3aff4ad2318ad6f"
        self.workspace_slug = "workspace-mq"
        self.plane_api = PlaneAPI(self.api_key_plane, self.workspace_slug)

    def reset_session(self):
        """Reset session state"""
        self.status = None
        self.pending_assignments = []
        self.project_id = None

    def extract_assignment_request(self, query, selected_history):
        """Trích xuất yêu cầu assignment từ query"""
        prompt = PROMPT_EXTRACT_ASSIGNMENT.format(
            query=query,
            history=selected_history or "Không có"
        )

        result = self.llm.generate_response(prompt, AssignmentRequest)

        if isinstance(result, list) and len(result) > 0:
            result = result[0]

        return result

    def get_unassigned_tasks(self, project_id):
        """Lấy danh sách tasks chưa được giao"""
        issues = self.plane_api.get_issues(project_id)
        unassigned = []

        for issue in issues:
            assignees = issue.get("assignees", [])
            if not assignees or len(assignees) == 0:
                unassigned.append(issue)

        return unassigned

    def suggest_assignments(self, tasks, project_id):
        """Sử dụng LLM để gợi ý phân công"""
        # Lấy thông tin members và workload
        workload = self.plane_api.get_member_workload(project_id)

        # Format tasks
        tasks_info = []
        for t in tasks:
            tasks_info.append({
                "id": t.get("id"),
                "name": t.get("name"),
                "priority": t.get("priority", "none"),
                "description": t.get("description_stripped", "")[:100]
            })

        # Format members
        members_info = []
        for member_id, info in workload.items():
            members_info.append({
                "id": member_id,
                "name": info.get("name"),
                "current_tasks": info.get("task_count", 0)
            })

        # Gọi LLM
        prompt = PROMPT_ASSIGNMENT.format(
            tasks=json.dumps(tasks_info, ensure_ascii=False, indent=2),
            members=json.dumps(members_info, ensure_ascii=False, indent=2)
        )

        result = self.llm.generate_response(prompt, AssignmentResult)

        if isinstance(result, list) and len(result) > 0:
            result = result[0]

        return result

    def format_suggestion_message(self, assignment_result):
        """Tạo message hiển thị gợi ý phân công"""
        msg = "Đây là gợi ý phân công tối ưu dựa trên tải công việc hiện tại:\n\n"

        # Group by member
        by_member = {}
        for item in assignment_result.assignments:
            member_name = item.member_name
            if member_name not in by_member:
                by_member[member_name] = []
            by_member[member_name].append(item.task_name)

        for member_name, tasks in by_member.items():
            msg += f"**{member_name}** - {len(tasks)} task:\n"
            for task in tasks:
                msg += f"  - {task}\n"
            msg += "\n"

        msg += f"\n{assignment_result.summary}\n\n"
        msg += "Bạn có muốn giao task theo gợi ý này không?"

        return msg

    def execute_assignments(self):
        """Thực hiện phân công trên Plane"""
        success_count = 0
        fail_count = 0

        for assignment in self.pending_assignments:
            task_id = assignment.task_id
            member_id = assignment.member_id

            result = self.plane_api.assign_issue(
                self.project_id,
                task_id,
                [member_id]
            )

            if result:
                success_count += 1
            else:
                fail_count += 1

        if fail_count == 0:
            return f"Tất cả {success_count} task đã được giao thành công!"
        else:
            return f"Đã giao {success_count} task thành công, {fail_count} task gặp lỗi."

    def handle_session(self, user_id, query, file_content=None, selected_history=None):
        """Xử lý session phân công task"""

        # Khởi tạo Plane API nếu chưa có
        if self.plane_api is None:
            self.get_info_plane(user_id)

        # Nếu đang chờ xác nhận
        if self.status == "waiting_confirmation":
            check_affirmative = self.affirmative_checker.check(query)

            if str(check_affirmative.is_affirmative).strip().lower() == "true":
                # Thực hiện phân công
                message = self.execute_assignments()
                self.reset_session()
                return None, message
            else:
                self.reset_session()
                return None, "Đã hủy phân công. Bạn có yêu cầu gì khác không?"

        # Extract yêu cầu từ query
        request = self.extract_assignment_request(query, selected_history)

        # Tìm project
        project = None
        if request and hasattr(request, 'project_name') and request.project_name:
            project = self.plane_api.find_project_by_name(request.project_name)
        else:
            # Lấy project đầu tiên
            projects = self.plane_api.get_projects()
            if projects:
                project = projects[0]

        if not project:
            return None, "Không tìm thấy dự án. Vui lòng chỉ định tên dự án."

        self.project_id = project.get("id")
        project_name = project.get("name")

        # Lấy tasks cần giao
        tasks_to_assign = []

        if request and hasattr(request, 'specific_tasks') and request.specific_tasks:
            # Giao các task cụ thể
            issues = self.plane_api.get_issues(self.project_id)
            for issue in issues:
                for task_name in request.specific_tasks:
                    if task_name.lower() in issue.get("name", "").lower():
                        tasks_to_assign.append(issue)
                        break
        else:
            # Giao các task chưa có assignee
            tasks_to_assign = self.get_unassigned_tasks(self.project_id)

            # Giới hạn số lượng nếu có
            if request and hasattr(request, 'task_count') and request.task_count and request.task_count > 0:
                tasks_to_assign = tasks_to_assign[:request.task_count]

        if not tasks_to_assign:
            return None, f"Không có task nào cần giao trong dự án '{project_name}'. Tất cả task đã được phân công."

        # Kiểm tra có members không
        members = self.plane_api.get_project_members(self.project_id)
        if not members:
            return None, f"Dự án '{project_name}' chưa có thành viên nào. Vui lòng thêm members trước."

        # Gợi ý phân công
        assignment_result = self.suggest_assignments(tasks_to_assign, self.project_id)

        # Lưu pending assignments
        if assignment_result and hasattr(assignment_result, 'assignments'):
            self.pending_assignments = assignment_result.assignments
        else:
            self.pending_assignments = []
        self.status = "waiting_confirmation"

        # Tạo message
        msg = f"Đang phân tích {len(tasks_to_assign)} task trong dự án '{project_name}'...\n\n"
        msg += self.format_suggestion_message(assignment_result)

        return "assignment", msg


# -----------------------------
# Test
# -----------------------------
if __name__ == "__main__":
    from llm.llm_client import LLMClient

    llm = LLMClient()
    session = SessionAssignment(llm)

    # Test queries
    test_queries = [
        "Giao task cho project AI2School",
        "Ok, làm theo gợi ý"
    ]

    for q in test_queries:
        session_state, response = session.handle_session("test_user", q)
        print(f"Q: {q}")
        print(f"State: {session_state}")
        print(f"A: {response}")
        print("-" * 50)
