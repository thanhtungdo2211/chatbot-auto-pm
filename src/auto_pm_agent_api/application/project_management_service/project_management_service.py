"""Project management service implementation for creating and updating projects."""

import logging
import re
from typing import Tuple, Optional

from pydantic import BaseModel, Field

from .plane_extractor import PlaneExtractor

logger = logging.getLogger(__name__)


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
# PROMPT LLM – FULL CRUD (Project + Task + Member)
# ============================================================
PROMPT_EXTRACT_UPDATE = """
Bạn là AI chuyên quản lý dữ liệu của hệ thống Plane.so.

🎯 Nhiệm vụ:
1) Phân loại yêu cầu người dùng thành một trong 8 hành động:
   - create_project
   - update_project
   - delete_project
   - create_task
   - update_task
   - delete_task
   - add_member   (thêm member từ workspace vào project)
   - remove_member (xóa member khỏi workspace/project)

2) Trích xuất đầy đủ các thông tin cần thiết để thực thi:
   - project_name / project_identifier / project (id/identifier/tên)
   - project_description
   - task_name
   - task_description
   - field
   - value
   - member_email
   - member_id (UUID) nếu xóa
   - role (mặc định 15)

📌 Hướng dẫn phân loại hành động:
- "tạo project", "new project", "thêm dự án" → create_project
- "tạo task", "thêm task", "thêm công việc" → create_task
- "cập nhật dự án", "sửa project" → update_project
- "cập nhật task", "sửa task", "đổi tên task" → update_task
- "xóa dự án", "delete project" → delete_project
- "xóa task", "delete task", "remove task" → delete_task
- "thêm member", "add member", "gán thành viên" → add_member
- "xóa member", "remove member", "kick member" → remove_member

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
🧠 Bổ sung ánh xạ từ ngữ:
- "mô tả" → description_html
- "deadline", "ngày hết hạn" → target_date
- "ngày bắt đầu" → start_date
- "ưu tiên" → priority
- "giao cho", "assign", "người làm" → assignees

Bạn PHẢI tự động ánh xạ (map) những từ này sang đúng field hợp lệ.

────────────────────────────────────────────
📋 Lịch sử hội thoại:
{history}

📋 Thông tin đã có trong session:
{existing_info}

📋 Yêu cầu người dùng hiện tại:
{query}

📋 Gợi ý sẵn có: email={email_hint}, project={project_hint}

────────────────────────────────────────────
🎯 Yêu cầu đầu ra:
Trả về JSON **đúng theo schema**, không giải thích thêm.

Schema:
{{
  "action_type": "...",
  "project": "...",
  "project_identifier": "...",
  "project_name": "...",
  "project_description": "...",
  "task_name": "...",
  "task_description": "...",
  "field": "...",
  "value": "...",
  "member_email": "...",
  "member_id": "...",
  "role": 15
}}
"""


class AddMemberRequest(BaseModel):
    """Thông tin cần để thêm member vào project."""

    project: Optional[str] = Field(None, description="ID/identifier/tên project")
    email: Optional[str] = Field(None, description="Email member cần thêm")
    role: int = Field(15, description="Role mặc định")


class UpdateExtractResult(BaseModel):
    """Thông tin LLM trích xuất cho thao tác cập nhật."""

    action_type: Optional[str] = Field(
        None,
        description="create_project | update_project | delete_project | create_task | update_task | delete_task | add_member | remove_member",
    )
    project: Optional[str] = Field(None, description="ID/identifier/tên project")
    project_identifier: Optional[str] = None
    project_name: Optional[str] = None
    project_description: Optional[str] = None
    task_name: Optional[str] = None
    task_description: Optional[str] = None
    field: Optional[str] = None
    value: Optional[str] = None
    member_email: Optional[str] = None
    member_id: Optional[str] = None
    role: Optional[int] = 15


class ProjectManagementService:
    """
    Service for managing project creation and updates.
    
    Handles the complete lifecycle of project management including:
    - Creating new projects from file uploads
    - Updating existing project information
    - Managing project sessions
    """

    def __init__(self, llm_client, plane_api_factory):
        """
        Initialize project management service.
        
        Args:
            llm_client: LLM client for AI operations
            plane_api_factory: Factory to create Plane API instances
        """
        self.llm = llm_client
        self.plane_api_factory = plane_api_factory
        self.plane_extractor = PlaneExtractor(llm_client)
        
        # Session state per user
        self.sessions = {}

    def handle_create_project(
        self,
        user_id: int,
        query: str,
        file_content: Optional[str],
        history: str
    ) -> Tuple[Optional[str], str]:
        """
        Handle project creation workflow.
        
        Args:
            user_id: User identifier
            query: User query
            file_content: File content for project extraction
            history: Conversation history
            
        Returns:
            Tuple of (session_state, response_message)
        """
        session = self.sessions.get(user_id, {})
        
        # Check if file content is provided
        if not session.get("status") and not file_content:
            return "create_new_project", "Vui lòng gửi thông tin để tạo project. Hiện tại dữ liệu về project sẽ được nhận từ file."
        
        # Extract project information from file
        if not session.get("status"):
            try:
                # Use LLM to extract project info
                extracted_data = self.plane_extractor.extract(file_content)
                logger.info(f"Extracted project data: {extracted_data}")
                
                # Check if valid project data
                if not extracted_data.is_info_project:
                    return None, "Dữ liệu từ file không hợp lệ. Vui lòng gửi đúng file chứa thông tin về project."
                
                if not extracted_data.project:
                    return None, "Không tìm thấy thông tin dự án trong file. Vui lòng kiểm tra lại."
                
                # Store extracted data in session
                session["status"] = "ready_to_create"
                session["extracted_data"] = extracted_data
                self.sessions[user_id] = session
                
                task_count = len(extracted_data.tasks) if extracted_data.tasks else 0
                return "create_new_project", f"Tôi đã trích xuất được thông tin dự án '{extracted_data.project.name}' với {task_count} công việc. Bạn có muốn tôi cập nhật dự án lên Plane không?"
                
            except Exception as e:
                logger.error(f"Error extracting project data: {e}", exc_info=True)
                return None, f"Đã xảy ra lỗi khi trích xuất thông tin dự án: {str(e)}"
        
        # Handle confirmation
        if session.get("status") == "ready_to_create":
            # Check if user confirms
            if self._is_affirmative(query):
                try:
                    # Get extracted data from session
                    extracted_data = session.get("extracted_data")
                    if not extracted_data:
                        self.sessions.pop(user_id, None)
                        return None, "Lỗi: Không tìm thấy dữ liệu dự án. Vui lòng thử lại."
                    
                    # Create project on Plane
                    plane_api = self.plane_api_factory.get_api(user_id)
                    
                    # Check if project already exists (to avoid 409 conflict)
                    existing_project = plane_api.find_project_by_name(extracted_data.project.name)
                    
                    if existing_project:
                        logger.info(f"Project '{extracted_data.project.name}' already exists, using existing project")
                        project_result = existing_project
                    else:
                        # Create the project - returns PlaneProject Pydantic object
                        project_result = plane_api.create_project(
                            name=extracted_data.project.name,
                            identifier=extracted_data.project.identifier,
                            description=extracted_data.project.description or ""
                        )
                        logger.info(f"Created project: {project_result.name} (ID: {project_result.id})")
                    
                    # Create tasks if available
                    created_tasks = 0
                    if extracted_data.tasks:
                        project_id = project_result.id  # Access as attribute, not dict
                        for task in extracted_data.tasks:
                            try:
                                plane_api.create_issue(
                                    project_id=project_id,
                                    name=task.name,
                                    description=task.description or "",
                                    start_date=task.start_date,
                                    target_date=task.target_date
                                )
                                created_tasks += 1
                                logger.info(f"Created task: {task.name}")
                            except Exception as e:
                                logger.error(f"Error creating task '{task.name}': {e}")
                    
                    self.sessions.pop(user_id, None)
                    
                    base_url = plane_api.base_url.replace("/api", "")
                    status_msg = "đã tồn tại và được cập nhật" if existing_project else "đã được tạo thành công"
                    return None, f"Dự án '{extracted_data.project.name}' {status_msg} với {created_tasks} công việc! Bạn có thể kiểm tra tại: {base_url}/projects/{project_result.id}/issues/"
                    
                except Exception as e:
                    logger.error(f"Error creating project on Plane: {e}", exc_info=True)
                    self.sessions.pop(user_id, None)
                    return None, f"Đã xảy ra lỗi khi tạo dự án trên Plane: {str(e)}"
            else:
                self.sessions.pop(user_id, None)
                return None, "Quá trình tạo dự án đã bị hủy. Bạn có yêu cầu gì khác không?"
        
        return None, "Xin lỗi, có lỗi trong quá trình xử lý."

    def handle_update_info(
        self,
        user_id: int,
        query: str,
        file_content: Optional[str],
        history: str
    ) -> Tuple[Optional[str], str]:
        """
        Handle project/task update workflow.
        
        Args:
            user_id: User identifier
            query: User query
            file_content: Optional file content
            history: Conversation history
            
        Returns:
            Tuple of (session_state, response_message)
        """
        session = self.sessions.get(user_id, {})
        
        # Extract update information
        if not session.get("status"):
            plane_api = self.plane_api_factory.get_api(user_id)
            try:
                update_req = self._extract_update_request(
                    query,
                    history,
                    existing_info=session.get("update_info"),
                )
            except Exception as e:
                logger.error("Lỗi trích xuất thông tin cập nhật: %s", e, exc_info=True)
                return None, "Không trích xuất được thông tin cập nhật. Vui lòng mô tả rõ thao tác."

            if update_req and update_req.action_type == "add_member":
                # Ưu tiên email/project từ LLM; fallback heuristic
                email = update_req.member_email or self._extract_email(query) or self._extract_email(history)
                project_key = (
                    update_req.project
                    or update_req.project_name
                    or update_req.project_identifier
                    or self._extract_project_hint(query)
                )
                role = update_req.role or 15

                if not email or not project_key:
                    return None, "Vui lòng cung cấp project (id/identifier/tên) và email của member cần thêm."

                project_obj = self._resolve_project(plane_api, project_key)
                if not project_obj:
                    return None, f"Không tìm thấy project tương ứng với '{project_key}'. Hãy cung cấp rõ hơn."

                # Validate email exists in workspace before asking confirmation
                if not self._member_exists(plane_api, email):
                    return None, (
                        f"Email {email} không tồn tại trong workspace. "
                        "Vui lòng kiểm tra lại hoặc thêm thành viên vào workspace trước."
                    )

                session["status"] = "waiting_confirmation"
                session["update_info"] = {
                    "action_type": "add_member",
                    "add_member": {
                        "project_id": project_obj.id,
                        "project_name": project_obj.name,
                        "email": email,
                        "role": role,
                    },
                }
                self.sessions[user_id] = session

                return (
                    "update_existing_information",
                    f"Thêm member {email} (role={role}) vào project {project_obj.name}. Bạn có xác nhận không?",
                )

            if update_req and update_req.action_type == "remove_member":
                member_id = update_req.member_id or self._extract_uuid(query)
                email = update_req.member_email or self._extract_email(query) or self._extract_email(history)

                if not (member_id or email):
                    return None, "Vui lòng cung cấp member_id hoặc email của member cần xóa."

                # Nếu chỉ có email, tìm member_id từ danh sách members
                if not member_id and email:
                    member_id = self._find_member_id_by_email(plane_api, email)
                    if not member_id:
                        return None, f"Không tìm thấy member với email {email}."

                session["status"] = "waiting_confirmation"
                session["update_info"] = {
                    "action_type": "remove_member",
                    "remove_member": {
                        "member_id": member_id,
                        "email": email,
                    },
                }
                self.sessions[user_id] = session

                return (
                    "update_existing_information",
                    f"Xóa member {email or member_id} khỏi workspace/project. Bạn có xác nhận không?",
                )

            # Chưa hỗ trợ các hành động khác
            try:
                prep_info, confirm_msg = self._prepare_general_update(plane_api, update_req)
            except ValueError as e:
                # Giữ session để người dùng có thể bổ sung thông tin hoặc hủy luồng
                session["status"] = "waiting_info"
                self.sessions[user_id] = session
                return "update_existing_information", str(e)
            if prep_info:
                session["status"] = "waiting_confirmation"
                session["update_info"] = prep_info
                self.sessions[user_id] = session
                return "update_existing_information", confirm_msg

            return None, "Không xử lý được yêu cầu cập nhật. Vui lòng cung cấp rõ hơn."
        
        # Handle confirmation
        if session.get("status") == "waiting_confirmation":
            if self._is_affirmative(query):
                # Execute update
                plane_api = self.plane_api_factory.get_api(user_id)
                add_member_info = session.get("update_info", {}).get("add_member")
                remove_member_info = session.get("update_info", {}).get("remove_member")
                general_info = session.get("update_info", {}) if session.get("update_info", {}).get("action_type") not in ["add_member", "remove_member"] else None
                member_msg = ""
                if add_member_info:
                    try:
                        plane_api.add_member_to_project(
                            project_id=add_member_info["project_id"],
                            email=add_member_info["email"],
                            role=add_member_info["role"],
                        )
                        member_msg = (
                            f"Đã thêm member {add_member_info['email']} vào project "
                            f"{add_member_info['project_name']}."
                        )
                    except Exception as e:
                        logger.error("Error adding member to project: %s", e, exc_info=True)
                        member_msg = "Không thể thêm member vào project."
                if remove_member_info:
                    try:
                        plane_api.remove_member_from_workspace(
                            member_id=remove_member_info["member_id"]
                        )
                        member_msg = (
                            f"Đã xóa member {remove_member_info.get('email') or remove_member_info['member_id']} khỏi workspace."
                        )
                    except Exception as e:
                        logger.error("Error removing member from workspace: %s", e, exc_info=True)
                        member_msg = "Không thể xóa member khỏi workspace."
                if general_info:
                    try:
                        member_msg = self._execute_update_action(plane_api, general_info)
                    except Exception as e:
                        logger.error("Error executing update action: %s", e, exc_info=True)
                        member_msg = "Không thể thực hiện cập nhật."
                
                self.sessions.pop(user_id, None)
                return None, f"Cập nhật thành công! {member_msg}".strip()
            else:
                self.sessions.pop(user_id, None)
                return None, "Đã hủy cập nhật."
        
        return None, "Xin lỗi, có lỗi trong quá trình xử lý."

    def _is_affirmative(self, query: str) -> bool:
        """Check if query is affirmative."""
        affirmative_words = ["có", "yes", "ok", "đồng ý", "chắc chắn"]
        return any(word in query.lower() for word in affirmative_words)

    def summarize_update_session(self, user_id: int) -> str:
        """Tóm tắt trạng thái luồng update để bot nhắc lại cho người dùng."""
        session = self.sessions.get(user_id, {})
        status = session.get("status")
        if not status:
            return ""

        if status == "waiting_info":
            return (
                "Bạn đang ở luồng cập nhật và bot đang chờ bạn bổ sung thông tin "
                "(project/task/field/giá trị) trước khi xác nhận."
            )

        if status == "waiting_confirmation":
            info = session.get("update_info") or {}
            summary = self._format_update_summary(info)
            if summary:
                return f"Đang chờ bạn xác nhận: {summary}"

        return ""

    def _format_update_summary(self, info: dict) -> str:
        """Sinh mô tả ngắn gọn cho yêu cầu update còn pending."""
        action = (info or {}).get("action_type")
        if not action:
            return ""

        if action == "add_member":
            add = info.get("add_member") or {}
            return (
                f"Thêm member {add.get('email')} (role={add.get('role')}) "
                f"vào project {add.get('project_name')}."
            )

        if action == "remove_member":
            rm = info.get("remove_member") or {}
            return f"Xóa member {rm.get('email') or rm.get('member_id')} khỏi workspace/project."

        if action == "update_project":
            return (
                f"Cập nhật project '{info.get('project_name')}': "
                f"{info.get('field')} -> {info.get('value')}."
            )

        if action == "delete_project":
            return f"Xóa project '{info.get('project_name')}'."

        if action == "create_task":
            return f"Tạo task '{info.get('task_name')}' trong project '{info.get('project_name')}'."

        if action == "update_task":
            return (
                f"Cập nhật task '{info.get('task_name')}' trong project '{info.get('project_name')}': "
                f"{info.get('field')} -> {info.get('value')}."
            )

        if action == "delete_task":
            return (
                f"Xóa task '{info.get('task_name')}' khỏi project '{info.get('project_name')}'."
            )

        if action == "create_project":
            return f"Tạo project '{info.get('project_name')}'."

        return ""


    def _extract_update_request(
        self,
        query: str,
        history: str,
        existing_info: Optional[dict] = None,
    ) -> UpdateExtractResult:
        """Dùng LLM trích xuất hành động cập nhật (bao gồm add_member)."""
        email_hint = self._extract_email(query) or self._extract_email(history)
        project_hint = self._extract_project_hint(query)
        prompt = PROMPT_EXTRACT_UPDATE.format(
            history=history or "Không có",
            existing_info=existing_info or "Không có",
            query=query,
            email_hint=email_hint or "chưa có",
            project_hint=project_hint or "chưa có",
        )
        result = self.llm.generate_response(prompt, output_format=UpdateExtractResult)
        if isinstance(result, UpdateExtractResult):
            parsed = result
        elif isinstance(result, dict):
            parsed = UpdateExtractResult(**result)
        else:
            raise ValueError("LLM không trả về định dạng UpdateExtractResult")

        if not parsed.member_email and email_hint:
            parsed.member_email = email_hint
        if not (parsed.project or parsed.project_identifier or parsed.project_name) and project_hint:
            parsed.project = project_hint
        if not parsed.member_id:
            parsed.member_id = self._extract_uuid(query) or self._extract_uuid(history)
        if not parsed.role:
            parsed.role = 15
        return parsed

    def _member_exists(self, plane_api, email: str) -> bool:
        """Check if an email exists in workspace members."""
        try:
            members = plane_api.list_members()
        except Exception as exc:
            logger.warning("Không lấy được danh sách members để kiểm tra email: %s", exc)
            return False
        email_norm = (email or "").strip().lower()
        for member in members or []:
            if isinstance(member, dict):
                mem_email = member.get("email", "") or ""
            else:
                mem_email = getattr(member, "email", None) or ""
            if mem_email.lower() == email_norm:
                return True
        return False

    def _prepare_general_update(self, plane_api, update_req: UpdateExtractResult):
        """Chuẩn bị dữ liệu cho các action project/task."""
        if not update_req or not update_req.action_type:
            raise ValueError("Không xác định được hành động cập nhật.")

        action = update_req.action_type
        action_lower = action.lower()

        # Resolve project if needed
        project_obj = None
        if action_lower in ["create_task", "update_task", "delete_task", "update_project", "delete_project", "create_project"]:
            project_key = (
                update_req.project
                or update_req.project_name
                or update_req.project_identifier
                or self._extract_project_hint(update_req.project or update_req.project_name or "")
            )
            if action_lower != "create_project":
                if not project_key:
                    raise ValueError("Vui lòng cung cấp project (id/identifier/tên).")
                project_obj = self._resolve_project(plane_api, project_key)
                if not project_obj:
                    raise ValueError(f"Không tìm thấy project tương ứng với '{project_key}'.")

        # Normalize field
        field = self._normalize_field(update_req.field, is_project=action_lower.startswith("update_project")) if update_req.field else None

        # Build update info per action
        if action_lower == "create_project":
            if not update_req.project_name:
                raise ValueError("Vui lòng cung cấp tên project để tạo.")
            info = {
                "action_type": "create_project",
                "project_name": update_req.project_name,
                "project_description": update_req.project_description or "",
            }
            confirm = f"Tạo project '{update_req.project_name}'. Bạn có xác nhận không?"
            return info, confirm

        if action_lower == "update_project":
            if not field or field not in PROJECT_UPDATE_FIELDS:
                raise ValueError(f"Field '{update_req.field}' không hợp lệ cho project.")
            if update_req.value is None:
                raise ValueError("Vui lòng cung cấp giá trị mới để cập nhật project.")
            info = {
                "action_type": "update_project",
                "project_id": project_obj.id,
                "project_name": project_obj.name,
                "field": field,
                "value": update_req.value,
            }
            confirm = (
                f"Cập nhật project '{project_obj.name}': {field} -> {update_req.value}. "
                "Bạn có xác nhận không?"
            )
            return info, confirm

        if action_lower == "delete_project":
            info = {
                "action_type": "delete_project",
                "project_id": project_obj.id,
                "project_name": project_obj.name,
            }
            confirm = f"Xóa project '{project_obj.name}'. Bạn có xác nhận không?"
            return info, confirm

        if action_lower == "create_task":
            if not update_req.task_name:
                raise ValueError("Vui lòng cung cấp tên task để tạo.")
            info = {
                "action_type": "create_task",
                "project_id": project_obj.id,
                "project_name": project_obj.name,
                "task_name": update_req.task_name,
                "task_description": update_req.task_description or "",
            }
            confirm = (
                f"Tạo task '{update_req.task_name}' trong project '{project_obj.name}'. "
                "Bạn có xác nhận không?"
            )
            return info, confirm

        if action_lower == "update_task":
            if not field or field not in ISSUE_UPDATE_FIELDS:
                raise ValueError(f"Field '{update_req.field}' không hợp lệ cho task.")
            if update_req.value is None:
                raise ValueError("Vui lòng cung cấp giá trị mới để cập nhật task.")

            issue = self._resolve_issue(plane_api, project_obj.id, update_req.task_name)
            if not issue:
                raise ValueError(f"Không tìm thấy task '{update_req.task_name}' trong project.")

            info = {
                "action_type": "update_task",
                "project_id": project_obj.id,
                "project_name": project_obj.name,
                "issue_id": issue.id,
                "task_name": issue.name,
                "field": field,
                "value": update_req.value,
            }
            confirm = (
                f"Cập nhật task '{issue.name}' trong project '{project_obj.name}': "
                f"{field} -> {update_req.value}. Bạn có xác nhận không?"
            )
            return info, confirm

        if action_lower == "delete_task":
            issue = self._resolve_issue(plane_api, project_obj.id, update_req.task_name)
            if not issue:
                raise ValueError(f"Không tìm thấy task '{update_req.task_name}' trong project.")
            info = {
                "action_type": "delete_task",
                "project_id": project_obj.id,
                "project_name": project_obj.name,
                "issue_id": issue.id,
                "task_name": issue.name,
            }
            confirm = (
                f"Xóa task '{issue.name}' khỏi project '{project_obj.name}'. Bạn có xác nhận không?"
            )
            return info, confirm

        raise ValueError("Hành động chưa được hỗ trợ.")

    def _resolve_project(self, plane_api, project_key: str):
        """Tìm project theo id/identifier/tên."""
        try:
            projects = plane_api.list_projects()
        except Exception as e:
            logger.error("Không lấy được danh sách project: %s", e, exc_info=True)
            return None

        key_lower = project_key.lower()
        for p in projects:
            if (
                key_lower == p.id.lower()
                or (p.identifier and key_lower == p.identifier.lower())
                or key_lower in p.name.lower()
            ):
                return p
        return None

    def _resolve_issue(self, plane_api, project_id: str, task_key: str):
        """Tìm issue theo id hoặc tên trong một project."""
        issues = plane_api.list_issues(project_id=project_id)
        task_lower = task_key.lower()
        for issue in issues:
            if task_lower == issue.id.lower() or task_lower == issue.name.lower():
                return issue
            if task_lower in issue.name.lower():
                return issue
        return None

    def _normalize_field(self, field: Optional[str], is_project: bool = False) -> Optional[str]:
        """Chuẩn hóa field theo mapping thân thiện."""
        if not field:
            return None
        key = field.strip().lower()
        mapped = FRIENDLY_FIELD_MAP.get(key, key)
        if is_project and mapped == "description_html":
            mapped = "description"
        return mapped

    def _extract_email(self, text: Optional[str]) -> Optional[str]:
        """Heuristic để tìm email trong text."""
        if not text:
            return None
        match = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)
        return match.group(0) if match else None

    def _extract_project_hint(self, text: Optional[str]) -> Optional[str]:
        """
        Heuristic đơn giản lấy từ/chuỗi có vẻ là identifier hoặc uuid trong text
        (để đưa vào prompt cho LLM).
        """
        if not text:
            return None
        uuid_match = re.search(
            r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
            text,
        )
        if uuid_match:
            return uuid_match.group(0)
        ident_match = re.search(r"\b[A-Z]{2,6}\b", text)
        if ident_match:
            return ident_match.group(0)
        return None

    def _extract_uuid(self, text: Optional[str]) -> Optional[str]:
        """Heuristic lấy UUID trong text."""
        if not text:
            return None
        match = re.search(
            r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
            text,
        )
        return match.group(0) if match else None

    def _find_member_id_by_email(self, plane_api, email: str) -> Optional[str]:
        """Tìm member id theo email trong workspace."""
        try:
            members = plane_api.list_members()
        except Exception as e:
            logger.error("Không lấy được danh sách members: %s", e, exc_info=True)
            return None
        for m in members:
            if getattr(m, "email", None) == email:
                return m.id
        return None

    def _execute_update_action(self, plane_api, info: dict) -> str:
        """Thực thi hành động update/create/delete project/task."""
        action = info.get("action_type")
        if action == "create_project":
            plane_api.create_project(
                name=info["project_name"],
                identifier=info["project_name"][:6],
                description=info.get("project_description", ""),
            )
            return f"Đã tạo project '{info['project_name']}'."

        if action == "update_project":
            plane_api.update_project(
                project_id=info["project_id"],
                **{info["field"]: info["value"]},
            )
            return (
                f"Đã cập nhật project '{info['project_name']}': "
                f"{info['field']} -> {info['value']}."
            )

        if action == "delete_project":
            plane_api.delete_project(project_id=info["project_id"])
            return f"Đã xóa project '{info['project_name']}'."

        if action == "create_task":
            plane_api.create_issue(
                project_id=info["project_id"],
                name=info["task_name"],
                description=info.get("task_description", ""),
            )
            return (
                f"Đã tạo task '{info['task_name']}' trong project '{info['project_name']}'."
            )

        if action == "update_task":
            plane_api.update_issue(
                project_id=info["project_id"],
                issue_id=info["issue_id"],
                **{info["field"]: info["value"]},
            )
            return (
                f"Đã cập nhật task '{info['task_name']}': "
                f"{info['field']} -> {info['value']}."
            )

        if action == "delete_task":
            plane_api.delete_issue(
                project_id=info["project_id"],
                issue_id=info["issue_id"],
            )
            return f"Đã xóa task '{info['task_name']}' khỏi project '{info['project_name']}'."

        raise ValueError("Hành động chưa được hỗ trợ.")
