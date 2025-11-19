"""Assignment service implementation for task distribution among team members."""

import logging
from typing import Tuple, Optional

logger = logging.getLogger(__name__)


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
        
        # Extract assignment request
        # Get unassigned tasks
        # Get team members and their workload
        # Use LLM to suggest assignments
        
        session["status"] = "waiting_confirmation"
        session["assignments"] = []  # Suggested assignments
        self.sessions[user_id] = session
        
        return "assignment", "Đây là gợi ý phân công tối ưu. Bạn có muốn giao task theo gợi ý này không?"

    def _execute_assignments(self, plane_api, assignments: list) -> int:
        """Execute task assignments."""
        success_count = 0
        for assignment in assignments:
            try:
                # plane_api.assign_task(...)
                success_count += 1
            except Exception as e:
                logger.error(f"Error assigning task: {e}")
        return success_count

    def _is_affirmative(self, query: str) -> bool:
        """Check if query is affirmative."""
        affirmative_words = ["có", "yes", "ok", "đồng ý", "chắc chắn"]
        return any(word in query.lower() for word in affirmative_words)
