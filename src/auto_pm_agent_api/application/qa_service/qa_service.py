"""QA service implementation for answering questions about projects and tasks."""

import logging
from typing import Tuple, Optional, List, Dict, Any

logger = logging.getLogger(__name__)


class QAService:
    """
    Service for answering questions about projects, tasks, and members.
    
    Uses RAG (Retrieval Augmented Generation) to provide accurate answers
    based on real-time data from the project management system.
    """

    def __init__(self, llm_client, plane_api_factory):
        """
        Initialize QA service.
        
        Args:
            llm_client: LLM client for AI operations
            plane_api_factory: Factory to create Plane API instances
        """
        self.llm = llm_client
        self.plane_api_factory = plane_api_factory

    def handle_query(
        self,
        user_id: int,
        query: str
    ) -> Tuple[Optional[str], str]:
        """
        Handle a QA query about projects/tasks.
        
        Args:
            user_id: User identifier
            query: User question
            
        Returns:
            Tuple of (session_state, response_message)
        """
        try:
            # Get Plane API
            plane_api = self.plane_api_factory.get_api(user_id)
            logger.info(f"Fetching data for user {user_id}")
            
            # Fetch relevant data
            data = self._fetch_project_data(plane_api)
            logger.info(f"Fetched {len(data)} data items for QA")
            
            if not data:
                return None, "Không tìm thấy dữ liệu dự án nào. Vui lòng kiểm tra kết nối với Plane API."
            
            # Format context for LLM
            context = self._format_context(data)
            
            # Generate answer using LLM with RAG
            from auto_pm_agent_api.domain.prompts import PROMPT_QA_RAG

            prompt = PROMPT_QA_RAG.format(
                context=context,
                query=query,
                history="Không có lịch sử"
            )
            
            response = self.llm.generate_response(prompt)
            
            return None, response
            
        except Exception as e:
            logger.error(f"Error in QA service: {e}", exc_info=True)
            return None, f"Đã xảy ra lỗi khi xử lý câu hỏi: {str(e)}"

    def _fetch_project_data(self, plane_api) -> List[Dict[str, Any]]:
        """
        Fetch all relevant project data from Plane API.
        
        This includes:
        - All projects in the workspace
        - All issues/tasks for each project
        - Workspace members (if available)
        
        Returns:
            List of dictionaries containing normalized data
        """
        data = []
        
        try:
            logger.info("Starting to fetch project data from Plane API...")
            
            # 1. Fetch workspace information
            try:
                logger.info("Fetching workspace information...")
                workspace = plane_api.get_workspace()
                logger.info(f"✓ Workspace: {workspace.get('name', 'Unknown')}")
            except Exception as e:
                logger.warning(f"Could not fetch workspace info: {e}")
                workspace = {}
            
            # 2. Fetch all projects
            try:
                logger.info("Fetching all projects...")
                projects = plane_api.list_projects()
                logger.info(f"✓ Found {len(projects)} project(s)")
                
                for project in projects:
                    # Add project to data
                    project_data = {
                        "type": "project",
                        "id": project.id,
                        "name": project.name,
                        "identifier": project.identifier,
                        "description": project.description or "Không có mô tả",
                        "workspace": project.workspace
                    }
                    data.append(project_data)
                    logger.info(f"  - Added project: {project.name} [{project.identifier}]")
                    
                    # 3. Fetch all issues/tasks for this project
                    try:
                        logger.info(f"  Fetching issues for project: {project.name}...")
                        issues = plane_api.list_issues(project_id=project.id)
                        logger.info(f"  ✓ Found {len(issues)} issue(s) in {project.name}")
                        
                        for issue in issues:
                            issue_data = {
                                "type": "task",
                                "id": issue.id,
                                "name": issue.name,
                                "description": issue.description or "Không có mô tả",
                                "project_id": project.id,
                                "project_name": project.name,
                                "project_identifier": project.identifier,
                                "state": issue.state or "Chưa xác định",
                                "priority": issue.priority or "Chưa đặt",
                                "assignee": issue.assignee or "Chưa gán"
                            }
                            data.append(issue_data)
                            
                    except Exception as e:
                        logger.warning(f"  ⚠ Could not fetch issues for project {project.name}: {e}")
                        continue
                        
            except Exception as e:
                logger.error(f"Error fetching projects: {e}", exc_info=True)
                raise
            
            # 4. Fetch workspace members (if endpoint is available)
            # Note: This depends on your Plane API version
            try:
                # Uncomment if you have a method to fetch members
                # members = plane_api.list_members()
                # for member in members:
                #     member_data = {
                #         "type": "member",
                #         "id": member.get("id"),
                #         "name": member.get("display_name") or member.get("email"),
                #         "role": member.get("role", "Member"),
                #         "email": member.get("email")
                #     }
                #     data.append(member_data)
                pass
            except Exception as e:
                logger.warning(f"Could not fetch members: {e}")
            
            logger.info(f"✓ Successfully fetched total {len(data)} data items")
            logger.info(f"  - Projects: {len([d for d in data if d['type'] == 'project'])}")
            logger.info(f"  - Tasks: {len([d for d in data if d['type'] == 'task'])}")
            logger.info(f"  - Members: {len([d for d in data if d['type'] == 'member'])}")
            
            return data
            
        except Exception as e:
            logger.error(f"Error in _fetch_project_data: {e}", exc_info=True)
            raise

    def _format_context(self, data: List[Dict[str, Any]]) -> str:
        """
        Format project data as context for LLM.
        
        Args:
            data: List of normalized data dictionaries
            
        Returns:
            Formatted context string in Vietnamese
        """
        if not data:
            return "Không có dữ liệu"
        
        # Separate by type
        projects = [d for d in data if d.get("type") == "project"]
        tasks = [d for d in data if d.get("type") == "task"]
        members = [d for d in data if d.get("type") == "member"]
        
        context_parts = []
        
        # Format projects section
        if projects:
            context_parts.append("=" * 60)
            context_parts.append("📁 DỰ ÁN (PROJECTS)")
            context_parts.append("=" * 60)
            for i, p in enumerate(projects, 1):
                context_parts.append(
                    f"\n{i}. **{p.get('name')}** [{p.get('identifier')}]\n"
                    f"   • ID: {p.get('id')}\n"
                    f"   • Mô tả: {p.get('description')}\n"
                )
        
        # Format tasks/issues section
        if tasks:
            context_parts.append("\n" + "=" * 60)
            context_parts.append("📋 CÔNG VIỆC (ISSUES/TASKS)")
            context_parts.append("=" * 60)
            
            # Group tasks by project
            tasks_by_project = {}
            for task in tasks:
                project_name = task.get('project_name')
                if project_name not in tasks_by_project:
                    tasks_by_project[project_name] = []
                tasks_by_project[project_name].append(task)
            
            for project_name, project_tasks in tasks_by_project.items():
                context_parts.append(f"\n📂 Dự án: {project_name}")
                for i, t in enumerate(project_tasks, 1):
                    priority_emoji = {
                        "urgent": "🔴",
                        "high": "🟠",
                        "medium": "🟡",
                        "low": "🟢",
                    }.get(str(t.get('priority', '')).lower(), "⚪")
                    
                    context_parts.append(
                        f"   {i}. {t.get('name')}\n"
                        f"      • Trạng thái: {t.get('state')}\n"
                        f"      • Độ ưu tiên: {priority_emoji} {t.get('priority')}\n"
                        f"      • Người nhận: {t.get('assignee')}\n"
                        f"      • Mô tả: {t.get('description')}\n"
                    )
        
        # Format members section
        if members:
            context_parts.append("\n" + "=" * 60)
            context_parts.append("👥 THÀNH VIÊN (MEMBERS)")
            context_parts.append("=" * 60)
            for i, m in enumerate(members, 1):
                context_parts.append(
                    f"\n{i}. {m.get('name')}\n"
                    f"   • Vai trò: {m.get('role')}\n"
                    f"   • Email: {m.get('email', 'N/A')}\n"
                )
        
        # Add summary
        context_parts.append("\n" + "=" * 60)
        context_parts.append("📊 TỔNG KẾT")
        context_parts.append("=" * 60)
        context_parts.append(f"• Tổng số dự án: {len(projects)}")
        context_parts.append(f"• Tổng số công việc: {len(tasks)}")
        if members:
            context_parts.append(f"• Tổng số thành viên: {len(members)}")
        
        return "\n".join(context_parts)
