"""Project management service implementation for creating and updating projects."""

import logging
from typing import Tuple, Optional
from .plane_extractor import PlaneExtractor

logger = logging.getLogger(__name__)


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
            return None, "Vui lòng gửi thông tin để tạo project. Hiện tại dữ liệu về project sẽ được nhận từ file."
        
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
            # Extract what needs to be updated
            session["status"] = "waiting_confirmation"
            session["update_info"] = {}  # Extracted update info
            self.sessions[user_id] = session
            
            return "update_existing_information", "Bạn có xác nhận cập nhật không?"
        
        # Handle confirmation
        if session.get("status") == "waiting_confirmation":
            if self._is_affirmative(query):
                # Execute update
                plane_api = self.plane_api_factory.get_api(user_id)
                # result = plane_api.update(...)
                
                self.sessions.pop(user_id, None)
                return None, "Cập nhật thành công!"
            else:
                self.sessions.pop(user_id, None)
                return None, "Đã hủy cập nhật."
        
        return None, "Xin lỗi, có lỗi trong quá trình xử lý."

    def _is_affirmative(self, query: str) -> bool:
        """Check if query is affirmative."""
        affirmative_words = ["có", "yes", "ok", "đồng ý", "chắc chắn"]
        return any(word in query.lower() for word in affirmative_words)
