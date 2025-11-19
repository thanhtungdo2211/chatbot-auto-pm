# # from pydantic import BaseModel, Field
# # from typing import Optional, List
# # import json
# # import sys
# # from pathlib import Path

# # # Add parent directory to path
# # FILE = Path(__file__).resolve()
# # ROOT = FILE.parents[1]
# # if str(ROOT) not in sys.path:
# #     sys.path.append(str(ROOT))

# # from session.session_create_project.update_plane import PlaneAPI
# # from session.session_create_project.check import AffirmativeChecker

# # # -----------------------------
# # # Prompt để extract thông tin cập nhật
# # # -----------------------------
# # PROMPT_EXTRACT_UPDATE = """
# # Bạn là một trợ lý AI, có nhiệm vụ trích xuất thông tin cập nhật từ yêu cầu của người dùng.

# # 🎯 Nhiệm vụ:
# # Phân tích yêu cầu cập nhật và trích xuất các thông tin sau:
# # - project_name: Tên dự án (nếu có)
# # - task_name: Tên task cần cập nhật
# # - field: Trường cần cập nhật (name, description, deadline/target_date, start_date, priority, state, assignee)
# # - value: Giá trị mới

# # 📋 Lịch sử hội thoại:
# # {history}

# # 📋 Thông tin đã có từ trước:
# # {existing_info}

# # ❓ Yêu cầu của người dùng:
# # {query}

# # ⚙️ Quy tắc:
# # 1. Trích xuất tất cả thông tin có thể từ yêu cầu và lịch sử chat nếu có liên hệ. 
# # 2. Nếu thiếu thông tin, để giá trị là null
# # 3. Với deadline/target_date: chuyển về định dạng YYYY-MM-DD
# # 4. Với priority: chuyển về giá trị (urgent, high, medium, low, none)
# # 5. Kết hợp với existing_info nếu có

# # Trả về JSON theo định dạng sau:
# # """

# # # -----------------------------
# # # Schema cho extract update
# # # -----------------------------
# # class UpdateExtractResult(BaseModel):
# #     project_name: Optional[str] = Field(None, description="Tên dự án")
# #     task_name: Optional[str] = Field(None, description="Tên task cần cập nhật")
# #     field: Optional[str] = Field(None, description="Trường cần cập nhật: name, description, target_date, start_date, priority, state, assignees")
# #     value: Optional[str] = Field(None, description="Giá trị mới")
# #     missing_fields: List[str] = Field(default_factory=list, description="Danh sách các trường còn thiếu")

# # # -----------------------------
# # # Session Update Info chính
# # # -----------------------------
# # class SessionUpdateInfo:
# #     def __init__(self, llm_client):
# #         self.llm = llm_client
# #         self.api_key_plane = None
# #         self.workspace_slug = None
# #         self.plane_api = None
# #         self.affirmative_checker = AffirmativeChecker(llm_client)

# #         # Session state
# #         self.status = None
# #         self.update_info = {}

# #     def get_info_plane(self, user_id):
# #         """Lấy thông tin Plane API từ user config"""
# #         self.api_key_plane = "plane_api_d958d52c6c0845cb94b8dadd7fef425e"
# #         self.workspace_slug = "thang"
# #         self.plane_api = PlaneAPI(self.api_key_plane, self.workspace_slug)

# #     def reset_session(self):
# #         """Reset session state"""
# #         self.status = None
# #         self.update_info = {}

# #     def extract_update_info(self, query, selected_history):
# #         """Trích xuất thông tin cập nhật từ query"""
# #         existing_info = json.dumps(self.update_info, ensure_ascii=False) if self.update_info else "Chưa có thông tin"

# #         prompt = PROMPT_EXTRACT_UPDATE.format(
# #             history=selected_history or "Không có",
# #             existing_info=existing_info,
# #             query=query
# #         )

# #         result = self.llm.generate_response(prompt, UpdateExtractResult)

# #         if isinstance(result, list) and len(result) > 0:
# #             result = result[0]

# #         return result

# #     def validate_update_info(self):
# #         """Kiểm tra xem đã đủ thông tin để cập nhật chưa"""
# #         required_fields = ["task_name", "field", "value"]
# #         missing = []

# #         for field in required_fields:
# #             if not self.update_info.get(field):
# #                 missing.append(field)

# #         return missing

# #     def get_field_display_name(self, field):
# #         """Lấy tên hiển thị của field"""
# #         field_names = {
# #             "task_name": "Tên task",
# #             "project_name": "Tên dự án",
# #             "field": "Trường cần cập nhật",
# #             "value": "Giá trị mới",
# #             "name": "Tên task",
# #             "description": "Mô tả",
# #             "target_date": "Deadline",
# #             "start_date": "Ngày bắt đầu",
# #             "priority": "Độ ưu tiên",
# #             "state": "Trạng thái",
# #             "assignees": "Người được giao"
# #         }
# #         return field_names.get(field, field)

# #     def format_confirmation_message(self):
# #         """Tạo message xác nhận cập nhật"""
# #         msg = "Tôi hiểu yêu cầu của bạn:\n\n"

# #         if self.update_info.get("project_name"):
# #             msg += f"- Dự án: {self.update_info['project_name']}\n"

# #         msg += f"- Task: {self.update_info.get('task_name', 'N/A')}\n"
# #         msg += f"- Trường cập nhật: {self.get_field_display_name(self.update_info.get('field', ''))}\n"
# #         msg += f"- Giá trị mới: {self.update_info.get('value', 'N/A')}\n\n"
# #         msg += "Bạn có xác nhận cập nhật không?"

# #         return msg

# #     def execute_update(self):
# #         """Thực hiện cập nhật trên Plane"""
# #         # Tìm project
# #         project_name = self.update_info.get("project_name")
# #         task_name = self.update_info.get("task_name")
# #         field = self.update_info.get("field")
# #         value = self.update_info.get("value")

# #         # Tìm project
# #         project = None
# #         if project_name:
# #             project = self.plane_api.find_project_by_name(project_name)
# #         else:
# #             # Tìm trong tất cả projects
# #             projects = self.plane_api.get_projects()
# #             for p in projects:
# #                 project_id = p.get("id")
# #                 issue = self.plane_api.find_issue_by_name(project_id, task_name)
# #                 if issue:
# #                     project = p
# #                     break

# #         if not project:
# #             return None, "Không tìm thấy dự án hoặc task phù hợp."

# #         project_id = project.get("id")

# #         # Tìm issue
# #         issue = self.plane_api.find_issue_by_name(project_id, task_name)
# #         if not issue:
# #             return None, f"Không tìm thấy task '{task_name}' trong dự án '{project.get('name')}'."

# #         issue_id = issue.get("id")

# #         # Chuẩn bị dữ liệu cập nhật
# #         update_data = {}

# #         # Map field names
# #         field_mapping = {
# #             "deadline": "target_date",
# #             "target_date": "target_date",
# #             "start_date": "start_date",
# #             "name": "name",
# #             "description": "description",
# #             "priority": "priority",
# #             "state": "state",
# #             "assignee": "assignees",
# #             "assignees": "assignees"
# #         }

# #         api_field = field_mapping.get(field.lower(), field)

# #         # Handle special fields
# #         if api_field == "assignees":
# #             # TODO: Convert member name to ID
# #             update_data[api_field] = [value]
# #         elif api_field == "state":
# #             # TODO: Convert state name to ID
# #             update_data[api_field] = value
# #         else:
# #             update_data[api_field] = value

# #         # Thực hiện cập nhật
# #         result = self.plane_api.update_issue(project_id, issue_id, update_data)

# #         if result:
# #             return result, f"Task '{task_name}' đã được cập nhật thành công! Trường '{self.get_field_display_name(field)}' đã được đổi thành '{value}'."
# #         else:
# #             return None, "Có lỗi xảy ra khi cập nhật. Vui lòng thử lại."

# #     def handle_session(self, user_id, query, file_content=None, selected_history=None):
# #         """Xử lý session cập nhật thông tin"""

# #         # Khởi tạo Plane API nếu chưa có
# #         if self.plane_api is None:
# #             self.get_info_plane(user_id)

# #         # Nếu đang chờ xác nhận
# #         if self.status == "waiting_confirmation":
# #             check_affirmative = self.affirmative_checker.check(query)

# #             if str(check_affirmative.is_affirmative).strip().lower() == "true":
# #                 # Thực hiện cập nhật
# #                 result, message = self.execute_update()
# #                 self.reset_session()
# #                 return None, message
# #             else:
# #                 self.reset_session()
# #                 return None, "Đã hủy cập nhật. Bạn có yêu cầu gì khác không?"

# #         # Nếu đang chờ bổ sung thông tin
# #         if self.status == "waiting_info":
# #             # Tiếp tục extract thông tin
# #             pass

# #         # Extract thông tin từ query
# #         result = self.extract_update_info(query, selected_history)

# #         # Cập nhật vào update_info
# #         if result and hasattr(result, 'project_name') and result.project_name:
# #             self.update_info["project_name"] = result.project_name
# #         if result and hasattr(result, 'task_name') and result.task_name:
# #             self.update_info["task_name"] = result.task_name
# #         if result and hasattr(result, 'field') and result.field:
# #             self.update_info["field"] = result.field
# #         if result and hasattr(result, 'value') and result.value:
# #             self.update_info["value"] = result.value

# #         # Kiểm tra thiếu thông tin
# #         missing = self.validate_update_info()

# #         if missing:
# #             self.status = "waiting_info"

# #             # Tạo message hỏi thông tin thiếu
# #             if "task_name" in missing:
# #                 return "update_existing_information", "Bạn muốn cập nhật task nào? Vui lòng cho tôi biết tên task."
# #             elif "field" in missing:
# #                 fields_list = "- Tên task (name)\n- Mô tả (description)\n- Deadline (target_date)\n- Ngày bắt đầu (start_date)\n- Độ ưu tiên (priority)\n- Trạng thái (state)\n- Người được giao (assignees)"
# #                 return "update_existing_information", f"Bạn muốn cập nhật trường nào của task '{self.update_info.get('task_name', '')}'?\n\n{fields_list}"
# #             elif "value" in missing:
# #                 field_name = self.get_field_display_name(self.update_info.get("field", ""))
# #                 return "update_existing_information", f"Bạn muốn đặt giá trị mới cho {field_name} là gì?"

# #         # Đã đủ thông tin - xác nhận với user
# #         self.status = "waiting_confirmation"
# #         confirmation_msg = self.format_confirmation_message()

# #         return "update_existing_information", confirmation_msg


# # # -----------------------------
# # # Test
# # # -----------------------------
# # if __name__ == "__main__":
# #     from llm.llm_client import LLMClient

# #     llm = LLMClient()
# #     session = SessionUpdateInfo(llm)

# #     # Test queries
# #     test_queries = [
# #         "Cập nhật deadline task 'Viết API Quiz' sang ngày 30/11/2025",
# #         "Có",
# #     ]

# #     for q in test_queries:
# #         session_state, response = session.handle_session("test_user", q)
# #         print(f"Q: {q}")
# #         print(f"State: {session_state}")
# #         print(f"A: {response}")
# #         print("-" * 50)
# from pydantic import BaseModel, Field
# from typing import Optional, List
# import json
# import sys
# from pathlib import Path

# # Add parent directory to path
# FILE = Path(__file__).resolve()
# ROOT = FILE.parents[1]
# if str(ROOT) not in sys.path:
#     sys.path.append(str(ROOT))

# from session.session_create_project.update_plane import PlaneAPI
# from session.session_create_project.check import AffirmativeChecker

# # -----------------------------
# # Prompt để extract thông tin cập nhật
# # -----------------------------
# PROMPT_EXTRACT_UPDATE = """
# Bạn là AI chuyên trích xuất thông tin cập nhật.

# 🎯 Nhiệm vụ:
# Xác định người dùng muốn cập nhật PROJECT hay TASK, sau đó trích xuất:

# - update_type: "project" hoặc "task"
# - project_name: tên dự án
# - task_name: tên task (nếu update task)
# - field: trường cần cập nhật
# - value: giá trị mới

# 📋 Lịch sử hội thoại:
# {history}

# 📋 Thông tin đã có:
# {existing_info}

# ❓ Yêu cầu người dùng:
# {query}

# ⚙️ Quy tắc:
# 1. Nếu người dùng đề cập đến project → update_type = "project"
# 2. Nếu đề cập đến task → update_type = "task"
# 3. Nếu không rõ → cố gắng suy luận từ context, hoặc để null
# 4. Dữ liệu thiếu → để null
# 5. Trả về JSON theo schema.
# """

# # -----------------------------
# # Schema extract
# # -----------------------------
# class UpdateExtractResult(BaseModel):
#     update_type: Optional[str] = Field(None, description="project/task")
#     project_name: Optional[str] = None
#     task_name: Optional[str] = None
#     field: Optional[str] = None
#     value: Optional[str] = None
#     missing_fields: List[str] = Field(default_factory=list)

# # -----------------------------
# # Session Update Info
# # -----------------------------
# class SessionUpdateInfo:
#     def __init__(self, llm_client):
#         self.llm = llm_client
#         self.plane_api = None
#         self.api_key_plane = None
#         self.workspace_slug = None
#         self.affirmative_checker = AffirmativeChecker(llm_client)

#         # state
#         self.status = None
#         self.update_info = {}

#     def get_info_plane(self, user_id):
#         self.api_key_plane = "plane_api_d958d52c6c0845cb94b8dadd7fef425e"
#         self.workspace_slug = "thang"
#         self.plane_api = PlaneAPI(self.api_key_plane, self.workspace_slug)

#     def reset_session(self):
#         self.status = None
#         self.update_info = {}

#     # -----------------------------
#     # Extract update info
#     # -----------------------------
#     def extract_update_info(self, query, selected_history):
#         existing = json.dumps(self.update_info, ensure_ascii=False) if self.update_info else "Chưa có"
#         prompt = PROMPT_EXTRACT_UPDATE.format(
#             history=selected_history or "Không có",
#             existing_info=existing,
#             query=query
#         )
#         result = self.llm.generate_response(prompt, UpdateExtractResult)

#         if isinstance(result, list):
#             result = result[0]

#         return result

#     # -----------------------------
#     # Validate thông tin theo loại update
#     # -----------------------------
#     def validate_update_info(self):
#         update_type = self.update_info.get("update_type")

#         if update_type == "project":
#             required = ["project_name", "field", "value"]
#         else:
#             required = ["task_name", "field", "value"]

#         missing = [r for r in required if not self.update_info.get(r)]
#         return missing

#     def format_confirmation_message(self):
#         msg = "Tôi hiểu yêu cầu của bạn:\n\n"

#         if self.update_info["update_type"] == "project":
#             msg += f"- Loại cập nhật: Dự án\n"
#             msg += f"- Dự án: {self.update_info.get('project_name')}\n"
#         else:
#             msg += f"- Loại cập nhật: Task\n"
#             msg += f"- Dự án: {self.update_info.get('project_name', 'Không rõ')}\n"
#             msg += f"- Task: {self.update_info.get('task_name')}\n"

#         msg += f"- Trường: {self.update_info.get('field')}\n"
#         msg += f"- Giá trị mới: {self.update_info.get('value')}\n\n"
#         msg += "Bạn có xác nhận cập nhật không?"

#         return msg

#     # -----------------------------
#     # Thực hiện cập nhật PROJECT
#     # -----------------------------
#     def execute_update_project(self):
#         project_name = self.update_info["project_name"]
#         field = self.update_info["field"]
#         value = self.update_info["value"]

#         project = self.plane_api.find_project_by_name(project_name)
#         if not project:
#             return None, f"Không tìm thấy dự án '{project_name}'."

#         project_id = project.get("id")

#         result = self.plane_api.update_project(project_id, {field: value})
#         if result:
#             return result, f"Dự án '{project_name}' đã được cập nhật trường '{field}' thành '{value}'."
#         else:
#             return None, "Lỗi khi cập nhật project."

#     # -----------------------------
#     # Thực hiện cập nhật TASK
#     # -----------------------------
#     def execute_update_task(self):
#         project_name = self.update_info.get("project_name")
#         task_name = self.update_info["task_name"]
#         field = self.update_info["field"]
#         value = self.update_info["value"]

#         # Tìm dự án
#         project = None
#         if project_name:
#             project = self.plane_api.find_project_by_name(project_name)
#         else:
#             # Scan toàn bộ dự án
#             for p in self.plane_api.get_projects():
#                 if self.plane_api.find_issue_by_name(p["id"], task_name):
#                     project = p
#                     break

#         if not project:
#             return None, f"Không tìm thấy project chứa task '{task_name}'."

#         project_id = project["id"]

#         # Tìm task
#         issue = self.plane_api.find_issue_by_name(project_id, task_name)
#         if not issue:
#             return None, f"Không tìm thấy task '{task_name}' trong dự án."

#         issue_id = issue["id"]

#         result = self.plane_api.update_issue(project_id, issue_id, {field: value})
#         if result:
#             return result, f"Task '{task_name}' đã được cập nhật trường '{field}' thành '{value}'."
#         else:
#             return None, "Lỗi khi cập nhật task."

#     # -----------------------------
#     # Điều phối update
#     # -----------------------------
#     def execute_update(self):
#         if self.update_info["update_type"] == "project":
#             return self.execute_update_project()
#         else:
#             return self.execute_update_task()

#     # -----------------------------
#     # MAIN SESSION
#     # -----------------------------
#     def handle_session(self, user_id, query, file_content=None, selected_history=None):

#         if self.plane_api is None:
#             self.get_info_plane(user_id)

#         # Người dùng đang xác nhận
#         if self.status == "waiting_confirmation":
#             check = self.affirmative_checker.check(query)
#             if str(check.is_affirmative).lower() == "true":
#                 result, msg = self.execute_update()
#                 self.reset_session()
#                 return None, msg
#             else:
#                 self.reset_session()
#                 return None, "Đã hủy cập nhật."

#         # Extract thông tin mới
#         result = self.extract_update_info(query, selected_history)

#         # Merge vào state
#         for f in ["update_type", "project_name", "task_name", "field", "value"]:
#             val = getattr(result, f, None)
#             if val:
#                 self.update_info[f] = val

#         # Validation
#         missing = self.validate_update_info()

#         if missing:
#             self.status = "waiting_info"

#             if "project_name" in missing:
#                 return "update_existing_information", "Bạn muốn cập nhật dự án nào?"
#             if "task_name" in missing:
#                 return "update_existing_information", "Bạn muốn cập nhật tên task nào?"
#             if "field" in missing:
#                 return "update_existing_information", "Bạn muốn cập nhật trường nào?"
#             if "value" in missing:
#                 return "update_existing_information", f"Giá trị mới cho {self.update_info.get('field')} là gì?"

#         # Đã đủ → hỏi xác nhận
#         self.status = "waiting_confirmation"
#         return "update_existing_information", self.format_confirmation_message()
















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


# ============================================================
# FIELD MAPPING CHUẨN PLANE
# ============================================================

PROJECT_UPDATE_FIELDS = [
    "name",
    "description",
    "emoji",
    "icon_prop",
    "cover_image",
    "project_lead",
    "default_assignee",
    "identifier",
    "estimate",
    "default_state",
    "module_view",
    "cycle_view",
    "issue_views_view",
    "page_view",
    "inbox_view",
]

ISSUE_UPDATE_FIELDS = [
    "name",
    "description_html",
    "priority",
    "start_date",
    "target_date",
    "estimate_point",
    "state",
    "assignees",
    "labels",
]

# Friendly → Plane mapping
FRIENDLY_FIELD_MAP = {
    "description": "description_html",
    "mô tả": "description_html",
    "deadline": "target_date",
    "due": "target_date",
    "start": "start_date",
    "bắt đầu": "start_date",
    "state": "state",
    "status": "state",
    "assignee": "assignees",
    "người làm": "assignees",
    "priority": "priority",
    "ưu tiên": "priority",
}


# ============================================================
# PROMPT LLM – FULL CRUD (Project + Task)
# ============================================================
PROMPT_EXTRACT_UPDATE = """
Bạn là AI chuyên quản lý dữ liệu của hệ thống Plane.so.

🎯 Nhiệm vụ:
1) Phân loại yêu cầu người dùng thành một trong 6 hành động:
   - create_project
   - update_project
   - delete_project
   - create_task
   - update_task
   - delete_task

2) Trích xuất đầy đủ các thông tin cần thiết để thực thi CRUD:
   - project_name
   - project_description
   - task_name
   - task_description
   - field
   - value

📌 Hướng dẫn phân loại hành động:
- "tạo project", "new project", "thêm dự án" → create_project
- "tạo task", "thêm task", "thêm công việc" → create_task
- "cập nhật dự án", "sửa project" → update_project
- "cập nhật task", "sửa task", "đổi tên task" → update_task
- "xóa dự án", "delete project" → delete_project
- "xóa task", "delete task", "remove task" → delete_task

────────────────────────────────────────────
🧩 DANH SÁCH TRƯỜNG (FIELD) HỢP LỆ TRONG PROJECT
────────────────────────────────────────────
Chỉ các trường sau được phép cập nhật cho PROJECT:

- name                → Tên dự án
- description         → Mô tả dự án
- identifier          → Mã viết tắt dự án (viết hoa, không dấu)

❗ Không được cập nhật các trường:
id, created_at, updated_at, created_by, updated_by, workspace, network, archive_in, close_in

────────────────────────────────────────────
🧩 DANH SÁCH TRƯỜNG (FIELD) HỢP LỆ TRONG TASK/ISSUE
────────────────────────────────────────────
Chỉ các trường sau được phép cập nhật cho TASK:

- name                  → Tên task
- description_html      → Mô tả dạng HTML
- description_stripped  → Mô tả dạng text
- priority              → Mức ưu tiên ("urgent" | "high" | "medium" | "low" | "none")
- start_date            → Ngày bắt đầu (YYYY-MM-DD)
- target_date           → Ngày kết thúc (YYYY-MM-DD)
- assignees             → Danh sách ID người được giao (array)


❗ Không được cập nhật các trường:
id, created_at, updated_at, project, workspace, sequence_id, sort_order, archived_at, completed_at

────────────────────────────────────────────
🧠 Bổ sung:
- Người dùng có thể dùng từ thuần Việt: "mô tả" → description_html
- "deadline", "ngày hết hạn" → target_date
- "ngày bắt đầu" → start_date
- "ưu tiên" → priority
- "giao cho", "assign" → assignees

Bạn PHẢI tự động ánh xạ (map) những từ này sang đúng field hợp lệ.

────────────────────────────────────────────
📋 Lịch sử hội thoại:
{history}

📋 Thông tin đã có trong session:
{existing_info}

📋 Yêu cầu người dùng hiện tại:
{query}

────────────────────────────────────────────
🎯 Yêu cầu đầu ra:
Trả về JSON **đúng theo schema**, không giải thích thêm.

Schema:
{{
  "action_type": "...",
  "project_name": "...",
  "project_description": "...",
  "task_name": "...",
  "task_description": "...",
  "field": "...",
  "value": "...",
  "missing_fields": []
}}
"""



# ============================================================
# SCHEMA LLM
# ============================================================
class UpdateExtractResult(BaseModel):
    action_type: Optional[str] = None
    project_name: Optional[str] = None
    project_description: Optional[str] = None
    task_name: Optional[str] = None
    task_description: Optional[str] = None
    field: Optional[str] = None
    value: Optional[str] = None


# ============================================================
# SESSION: CRUD PROJECT + TASK
# ============================================================
class SessionUpdateInfo:
    def __init__(self, llm_client):
        self.llm = llm_client
        self.plane_api = None
        self.affirmative_checker = AffirmativeChecker(llm_client)
        self.status = None
        self.update_info = {}

    def get_info_plane(self, user_id):
        """Load Plane API config"""
        self.api_key_plane = "plane_api_d958d52c6c0845cb94b8dadd7fef425e"
        self.workspace_slug = "thang"
        self.plane_api = PlaneAPI(self.api_key_plane, self.workspace_slug)

    def reset_session(self):
        self.status = None
        self.update_info = {}

    # ------------------------------------------------------------
    # Field normalize
    # ------------------------------------------------------------
    def normalize_field(self, field: str):
        if not field:
            return None
        field = field.lower().strip()
        return FRIENDLY_FIELD_MAP.get(field, field)

    # ============================================================
    # EXTRACT INFO FROM USER QUERY
    # ============================================================
    def extract_update_info(self, query, selected_history):
        existing = json.dumps(self.update_info, ensure_ascii=False) if self.update_info else "Không có"
        prompt = PROMPT_EXTRACT_UPDATE.format(
            history=selected_history or "Không có",
            existing_info=existing,
            query=query
        )
        result = self.llm.generate_response(prompt, UpdateExtractResult)
        return result[0] if isinstance(result, list) else result

    # ============================================================
    # VALIDATE INPUT DEPENDING ON ACTION
    # ============================================================
    def validate_update_info(self):
        action = self.update_info.get("action_type")

        rules = {
            "create_project": ["project_name"],
            "update_project": ["project_name", "field", "value"],
            "delete_project": ["project_name"],

            "create_task": ["task_name", "project_name"],
            "update_task": ["task_name", "field", "value"],
            "delete_task": ["task_name"],
        }

        required = rules.get(action, [])
        return [r for r in required if not self.update_info.get(r)]

    # ============================================================
    # CONFIRMATION MESSAGE
    # ============================================================
    def format_confirmation_message(self):
        info = self.update_info
        action = info["action_type"]

        msg = "Tôi hiểu yêu cầu của bạn:\n\n"
        msg += f"- Hành động: {action}\n"

        if info.get("project_name"):
            msg += f"- Dự án: {info['project_name']}\n"

        if info.get("task_name"):
            msg += f"- Task: {info['task_name']}\n"

        if action.startswith("update"):
            msg += f"- Trường: {info.get('field')}\n"
            msg += f"- Giá trị mới: {info.get('value')}\n"

        msg += "\nBạn có muốn xác nhận thao tác này không?"
        return msg

    # ============================================================
    # EXECUTE CREATE PROJECT
    # ============================================================
    def execute_create_project(self):
        name = self.update_info["project_name"]
        desc = self.update_info.get("project_description", "")

        result = self.plane_api.create_project(name=name, identifier=name[:6], description=desc)
        if result:
            return result, f"🎉 Dự án '{name}' đã được tạo thành công!"
        return None, "Không thể tạo dự án."

    # ============================================================
    # EXECUTE UPDATE PROJECT
    # ============================================================
    def execute_update_project(self):
        name = self.update_info["project_name"]
        field = self.normalize_field(self.update_info["field"])
        value = self.update_info["value"]

        if field not in PROJECT_UPDATE_FIELDS:
            return None, f"❌ Field '{field}' không hợp lệ cho dự án."

        project = self.plane_api.find_project_by_name(name)
        if not project:
            return None, f"Không tìm thấy dự án '{name}'."

        pid = project["id"]
        result = self.plane_api.update_project(pid, {field: value})

        if result:
            return result, f"✔ Dự án '{name}' đã được cập nhật."
        return None, "Lỗi khi cập nhật dự án."

    # ============================================================
    # EXECUTE DELETE PROJECT
    # ============================================================
    def execute_delete_project(self):
        name = self.update_info["project_name"]

        project = self.plane_api.find_project_by_name(name)
        if not project:
            return None, f"Không tìm thấy dự án '{name}'."

        ok = self.plane_api.delete_project(project["id"])
        if ok:
            return True, f"❌ Dự án '{name}' đã bị xoá vĩnh viễn."
        return None, "Không thể xoá dự án."

    # ============================================================
    # EXECUTE CREATE TASK
    # ============================================================
    def execute_create_task(self):
        pname = self.update_info["project_name"]
        tname = self.update_info["task_name"]
        desc = self.update_info.get("task_description", "")

        project = self.plane_api.find_project_by_name(pname)
        if not project:
            return None, f"Không tìm thấy dự án '{pname}'."

        pid = project["id"]
        data = {"name": tname, "description_html": desc}

        result = self.plane_api.create_task(pid, data)
        if result:
            return result, f"🎉 Task '{tname}' đã tạo thành công."
        return None, "Không thể tạo task."

    # ============================================================
    # EXECUTE UPDATE TASK
    # ============================================================
    def execute_update_task(self):
        pname = self.update_info.get("project_name")
        tname = self.update_info["task_name"]

        field = self.normalize_field(self.update_info["field"])
        value = self.update_info["value"]

        if field not in ISSUE_UPDATE_FIELDS:
            return None, f"❌ Field '{field}' không hợp lệ cho task."

        # Find project
        project = None
        if pname:
            project = self.plane_api.find_project_by_name(pname)
        else:
            for p in self.plane_api.get_projects():
                if self.plane_api.find_issue_by_name(p["id"], tname):
                    project = p
                    break

        if not project:
            return None, f"Không tìm thấy task '{tname}' trong bất kỳ dự án nào."

        pid = project["id"]
        issue = self.plane_api.find_issue_by_name(pid, tname)

        if not issue:
            return None, f"Task '{tname}' không tồn tại trong dự án."

        issue_id = issue["id"]
        result = self.plane_api.update_issue(pid, issue_id, {field: value})

        if result:
            return result, f"✔ Task '{tname}' đã được cập nhật."
        return None, "Không thể cập nhật task."

    # ============================================================
    # EXECUTE DELETE TASK
    # ============================================================
    def execute_delete_task(self):
        tname = self.update_info["task_name"]

        for p in self.plane_api.get_projects():
            issue = self.plane_api.find_issue_by_name(p["id"], tname)
            if issue:
                ok = self.plane_api.delete_issue(p["id"], issue["id"])
                if ok:
                    return True, f"❌ Task '{tname}' đã bị xoá."
                return None, "Không thể xoá task."
        return None, f"Không tìm thấy task '{tname}'."

    # ============================================================
    # DISPATCH ACTION
    # ============================================================
    def execute_action(self):
        action = self.update_info["action_type"]

        if action == "create_project":
            return self.execute_create_project()
        if action == "update_project":
            return self.execute_update_project()
        if action == "delete_project":
            return self.execute_delete_project()

        if action == "create_task":
            return self.execute_create_task()
        if action == "update_task":
            return self.execute_update_task()
        if action == "delete_task":
            return self.execute_delete_task()

        return None, "Hành động không hợp lệ."

    # ============================================================
    # MAIN SESSION HANDLER
    # ============================================================
    def handle_session(self, user_id, query, file_content=None, selected_history=None):

        if self.plane_api is None:
            self.get_info_plane(user_id)

        # ĐANG CHỜ XÁC NHẬN
        if self.status == "waiting_confirmation":
            check = self.affirmative_checker.check(query)

            if str(check.is_affirmative).lower() == "true":
                result, msg = self.execute_action()
                self.reset_session()
                return None, msg
            else:
                self.reset_session()
                return None, "Đã hủy thao tác."

        # Extract yêu cầu mới
        result = self.extract_update_info(query, selected_history)

        # Merge fields
        for f in [
            "action_type", "project_name", "project_description",
            "task_name", "task_description", "field", "value"
        ]:
            val = getattr(result, f, None)
            if val:
                self.update_info[f] = val

        # Validate
        missing = self.validate_update_info()

        if missing:
            self.status = "waiting_info"

            if "project_name" in missing:
                return "update_existing_information", "Bạn muốn thao tác với dự án nào?"
            if "task_name" in missing:
                return "update_existing_information", "Tên task là gì?"
            if "field" in missing:
                return "update_existing_information", "Bạn muốn cập nhật trường nào?"
            if "value" in missing:
                return "update_existing_information", f"Giá trị mới của '{self.update_info.get('field')}' là gì?"

        # ĐỦ THÔNG TIN → HỎI XÁC NHẬN
        self.status = "waiting_confirmation"
        return "update_existing_information", self.format_confirmation_message()
