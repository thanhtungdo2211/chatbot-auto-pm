"""Assignment service implementation for task distribution among team members."""

import logging
import os
from typing import Tuple, Optional, List, Dict, Any

import requests
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class SuggestedAssignment(BaseModel):
    """Structured suggestion for assigning a task."""
    issue_id: str = Field(..., description="ID của task cần giao")
    issue_name: str = Field(..., description="Tên task để tham khảo")
    assignee_id: str = Field(..., description="ID thành viên được giao")
    assignee_name: str = Field(..., description="Tên thành viên được giao")
    reason: Optional[str] = Field(None, description="Lý do lựa chọn")


class AssignmentPlan(BaseModel):
    """Container for all suggested assignments."""
    assignments: List[SuggestedAssignment] = Field(default_factory=list)
    rationale: Optional[str] = Field(None, description="Lý do tổng quát")


class AssignmentService:
    """
    Service for intelligent task assignment to team members.
    
    Uses AI to suggest optimal task distribution based on:
    - Current workload
    - Team member skills
    - Task priority
    - Balanced distribution
    """

    def __init__(self, llm_client, plane_api_factory):
        """
        Initialize assignment service.
        
        Args:
            llm_client: LLM client for AI operations
            plane_api_factory: Factory to create Plane API instances
        """
        self.llm = llm_client
        self.plane_api_factory = plane_api_factory
        
        # Session state per user
        self.sessions = {}

    def handle_assignment(
        self,
        user_id: int,
        query: str,
        history: str
    ) -> Tuple[Optional[str], str]:
        """
        Handle task assignment workflow.
        
        Args:
            user_id: User identifier
            query: User query
            history: Conversation history
            
        Returns:
            Tuple of (session_state, response_message)
        """
        session = self.sessions.get(user_id, {})
        plane_api = self.plane_api_factory.get_api(user_id)
        
        # Handle confirmation
        if session.get("status") == "waiting_confirmation":
            if self._is_affirmative(query):
                # Execute assignments
                assignments = session.get("assignments", [])
                success_count = self._execute_assignments(plane_api, assignments)
                
                self.sessions.pop(user_id, None)
                return None, f"Tất cả {success_count} task đã được giao thành công!"
            else:
                self.sessions.pop(user_id, None)
                return None, "Đã hủy phân công. Bạn có yêu cầu gì khác không?"
        
        # Extract assignment request: xác định project từ query
        plane_api = self.plane_api_factory.get_api(user_id)
        try:
            project, projects = self._select_project(plane_api, query)
        except Exception as e:
            logger.error("Error when selecting project: %s", e, exc_info=True)
            return None, "Không thể lấy thông tin project để phân công."

        if project is None:
            available = ", ".join([f"{p.name} ({p.identifier})" for p in projects]) or "không có"
            return "assignment", (
                "Bạn muốn phân công cho project nào? "
                f"Các project hiện có: {available}."
            )

        # Get unassigned tasks
        issues = plane_api.list_issues(project_id=project.id)
        unassigned_tasks = [issue for issue in issues if not issue.assignee]
        if not unassigned_tasks:
            return None, f"Tất cả task trong project {project.name} đã có người nhận."

        # Get team members and their workload
        members = plane_api.list_project_members(project.id) or plane_api.list_members()
        if not members:
            return None, "Không lấy được danh sách thành viên để phân công."

        workload = self._calculate_workload(issues, members)

        # Enrich member info from external profile API (e.g., Zalo webhook)
        enriched_members = self._enrich_members(members, workload)

        # Use LLM to suggest assignments
        plan = self._suggest_assignments(
            project_name=project.name,
            project_identifier=project.identifier or project.id,
            tasks=unassigned_tasks,
            members=enriched_members,
            history=history,
        )

        if not plan.assignments:
            return None, "Không thể tạo gợi ý phân công từ dữ liệu hiện có."

        session["status"] = "waiting_confirmation"
        session["assignments"] = [
            {
                "project_id": project.id,
                "issue_id": a.issue_id,
                "issue_name": a.issue_name,
                "assignee_id": a.assignee_id,
                "assignee_name": a.assignee_name,
                "reason": a.reason,
            }
            for a in plan.assignments
        ]
        self.sessions[user_id] = session

        summary_lines = [
            f"Gợi ý phân công cho project {project.name}:",
        ]
        for idx, assignment in enumerate(plan.assignments, 1):
            summary_lines.append(
                f"{idx}. {assignment.issue_name} -> {assignment.assignee_name} "
                f"({assignment.reason or 'cân bằng workload'})"
            )
        if plan.rationale:
            summary_lines.append(f"Lý do chung: {plan.rationale}")
        summary_lines.append("Bạn có muốn giao task theo gợi ý này không?")

        return "assignment", "\n".join(summary_lines)
        
    def _execute_assignments(self, plane_api, assignments: list) -> int:
        """Execute task assignments."""
        success_count = 0
        for assignment in assignments:
            try:
                project_id = assignment.get("project_id")
                issue_id = assignment.get("issue_id")
                assignee_id = assignment.get("assignee_id")
                if not (project_id and issue_id and assignee_id):
                    logger.warning("Bỏ qua assignment thiếu dữ liệu: %s", assignment)
                    continue
                plane_api.update_issue(
                    project_id=project_id,
                    issue_id=issue_id,
                    assignee=assignee_id,
                )
                success_count += 1
            except Exception as e:
                logger.error(f"Error assigning task: {e}")
        return success_count

    def _is_affirmative(self, query: str) -> bool:
        """Check if query is affirmative."""
        affirmative_words = ["có", "yes", "ok", "đồng ý", "chắc chắn"]
        return any(word in query.lower() for word in affirmative_words)

    def _select_project(self, plane_api, query: str):
        """Select a project based on user query."""
        projects = plane_api.list_projects()
        if not projects:
            raise ValueError("Không có project nào trong workspace.")

        query_lower = query.lower()
        for project in projects:
            name = (project.name or "").lower()
            ident = (project.identifier or "").lower()
            pid = (project.id or "").lower()
            if (
                (name and (name in query_lower or query_lower in name))
                or (ident and (ident in query_lower or query_lower in ident))
                or (pid and pid in query_lower)
            ):
                return project, projects

        if len(projects) == 1:
            return projects[0], projects

        return None, projects

    def _calculate_workload(self, issues, members) -> Dict[str, int]:
        """Count current tasks per member."""
        workload = {member.id: 0 for member in members}
        for issue in issues:
            assignee = str(issue.assignee) if issue.assignee else None
            if assignee in workload:
                workload[assignee] += 1
        return workload

    def _fetch_member_profile(
        self, member_id: Optional[str], email: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Fetch member profile from user service using member id; fallback by email."""
        base_url = os.getenv("USER_SERVICE_BASE_URL") or os.getenv("ZALO_WEBHOOK_BASE_URL")
        if not base_url:
            return None

        # Prefer user_id when available in member.id, otherwise fallback to email-based endpoint
        if member_id:
            url = f"{base_url.rstrip('/')}/api/users/{member_id}/with-zalo/"
        else:
            url = None

        try:
            if url:
                response = requests.get(url, timeout=10)
                if response.status_code == 404:
                    return None
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.warning("Không lấy được profile từ user service cho %s: %s", member_id, e)

        # Fallback to email-based webhook if available
        email_url = None
        if email and base_url:
            email_url = f"{base_url.rstrip('/')}/users/email/{email}"
        try:
            if email_url:
                response = requests.get(email_url, timeout=10)
                response.raise_for_status()
                data = response.json()
                if isinstance(data, dict) and data.get("status") == "success":
                    return data.get("user")
        except Exception as e:
            logger.warning("Không lấy được profile từ webhook cho %s: %s", email, e)
        return None

    def _enrich_members(self, members, workload: Dict[str, int]) -> List[Dict[str, Any]]:
        """Combine Plane members with external profile data."""
        enriched = []
        for member in members:
            profile = self._fetch_member_profile(member.id or member.email, email=member.email)
            zalo_meta = (profile or {}).get("zalo_metadata") or (profile or {}).get("cv_data") or {}
            enriched.append(
                {
                    "id": member.id,
                    "name": (
                        (profile or {}).get("display_name")
                        or f"{(profile or {}).get('first_name', '')} {(profile or {}).get('last_name', '')}".strip()
                        or member.display_name
                    ),
                    "email": member.email,
                    "role": member.role,
                    "workload": workload.get(member.id, 0),
                    "skills": zalo_meta.get("skills", []) or (profile or {}).get("skills", []),
                    "experience_years": zalo_meta.get("experience_years"),
                    "experience_level": zalo_meta.get("experience_level"),
                }
            )
        return enriched

    def _suggest_assignments(
        self,
        project_name: str,
        project_identifier: str,
        tasks,
        members: List[Dict[str, Any]],
        history: str,
    ) -> AssignmentPlan:
        """Call LLM to generate assignment suggestions."""
        task_lines = []
        for idx, task in enumerate(tasks, 1):
            task_lines.append(
                f"{idx}. {task.name} (id={task.id}, priority={task.priority}, state={task.state})"
            )

        member_lines = []
        for member in members:
            skills_txt = ", ".join(member.get("skills", [])) if member.get("skills") else "không rõ"
            member_lines.append(
                f"- {member.get('name')} (id={member.get('id')}, workload={member.get('workload')}, "
                f"role={member.get('role')}, skills={skills_txt}, exp_years={member.get('experience_years')})"
            )

        prompt = f"""
Bạn là một trợ lý PM. Hãy đề xuất phân công cho các task chưa có người nhận.

Project: {project_name} ({project_identifier})
Lịch sử hội thoại: {history}

Các task chưa giao:
{chr(10).join(task_lines)}

Danh sách thành viên (kèm workload hiện tại):
{chr(10).join(member_lines)}

Yêu cầu:
- Chỉ chọn thành viên từ danh sách trên.
- Ưu tiên cân bằng workload và phù hợp vai trò nếu có.
- Trả về JSON đúng schema: {{
    "assignments": [
        {{
            "issue_id": "...",
            "issue_name": "...",
            "assignee_id": "...",
            "assignee_name": "...",
            "reason": "..."
        }}
    ],
    "rationale": "..."
}}
- Không tạo thêm thành viên hay task mới.
"""

        try:
            result = self.llm.generate_response(prompt, output_format=AssignmentPlan)
            if isinstance(result, AssignmentPlan):
                return result
            if isinstance(result, dict):
                return AssignmentPlan(**result)
        except Exception as e:
            logger.error("LLM assignment suggestion failed: %s", e, exc_info=True)

        return AssignmentPlan(assignments=[], rationale="LLM không trả về gợi ý hợp lệ.")
