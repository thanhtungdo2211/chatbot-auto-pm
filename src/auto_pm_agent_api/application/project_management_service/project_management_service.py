"""Project management service implementation for creating and updating projects."""

from typing import Tuple, Optional


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
            # Use LLM to extract project info
            # This would call the plane extractor
            session["status"] = "ready_to_create"
            session["project_data"] = {}  # Extracted data
            self.sessions[user_id] = session
            
            return "create_new_project", "Tôi đã trích xuất được thông tin dự án. Bạn có muốn tôi cập nhật dự án lên Plane không?"
        
        # Handle confirmation
        if session.get("status") == "ready_to_create":
            # Check if user confirms
            if self._is_affirmative(query):
                # Create project on Plane
                plane_api = self.plane_api_factory.get_api(user_id)
                # result = plane_api.create_project(...)
                
                self.sessions.pop(user_id, None)
                return None, "Dự án đã được tạo thành công! Bạn có thể kiểm tra trên Plane."
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
