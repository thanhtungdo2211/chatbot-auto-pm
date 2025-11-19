"""Main chat service implementation orchestrating all user interactions."""

import logging
from typing import Optional, Tuple

from auto_pm_agent_api.domain.memory import MemoryInterface
from auto_pm_agent_api.domain.tools import IntentClassifier
from auto_pm_agent_api.application.project_management_service import ProjectManagementService
from auto_pm_agent_api.application.qa_service import QAService
from auto_pm_agent_api.application.assignment_service import AssignmentService

logger = logging.getLogger(__name__)


class ChatService:
    """
    Main chat service that handles user queries and orchestrates different services.
    
    This service acts as the main orchestrator for all chat interactions, routing
    queries to appropriate specialized services based on intent classification.
    """

    def __init__(
        self,
        memory: MemoryInterface,
        intent_classifier: IntentClassifier,
        project_service: ProjectManagementService,
        qa_service: QAService,
        assignment_service: AssignmentService,
        general_bot,  # LLM-based general bot for other topics
    ):
        self.memory = memory
        self.intent_classifier = intent_classifier
        self.project_service = project_service
        self.qa_service = qa_service
        self.assignment_service = assignment_service
        self.general_bot = general_bot
        
        # Track active sessions by user_id
        self.active_sessions = {}

    def handle_query(
        self,
        user_id: int,
        query: Optional[str] = None,
        file_content: Optional[str] = None,
    ) -> str:
        """
        Handle a user query and return a response.
        
        Args:
            user_id: User identifier
            query: User query text
            file_content: Optional file content for project creation
            
        Returns:
            Response string
        """
        logger.info(f"User {user_id} sent query: {query[:100] if query else 'None'}")

        # Handle file upload
        if file_content and file_content.strip():
            self.active_sessions[user_id] = {
                "file_content": file_content,
                "session_type": None
            }
            return "Tôi đã hoàn tất đọc file. Hiện tại dữ liệu từ file sẽ được lưu để tạo thông tin về project."
        
        # Get relevant conversation history
        selected_history = self.memory.select_relevant_history(user_id, query)
        history_str = selected_history.to_string()

        # Check if there's an active session
        active_session = self.active_sessions.get(user_id)
        
        if active_session and active_session.get("session_type"):
            # Route to the active session
            session_type = active_session["session_type"]
            file_content = active_session.get("file_content")
            
            session, response = self._route_to_session(
                user_id, session_type, query, file_content, history_str
            )
            # print(f"Routed to active session: {session_type} with response: {response[:100]}")
            # Save to memory
            self.memory.add_message(user_id, "user", query)
            self.memory.add_message(user_id, "chatbot", response)
            
            # Update or clear session
            if session is None:
                self.active_sessions.pop(user_id, None)
            else:
                self.active_sessions[user_id]["session_type"] = session
                
            return response

        # No active session - classify intent
        intent_result = self.intent_classifier.classify(history_str, query)
        intent = intent_result.intent
        
        logger.info(f"Classified intent: {intent}")

        # Route based on intent
        if intent == "other_topics":
            response = self.general_bot.generate_response(history_str, query)
            
        elif intent in ["create_new_project", "update_existing_information", 
                       "update_plane_information"]:
            file_content = active_session.get("file_content") if active_session else None
            session, response = self._route_to_session(
                user_id, intent, query, file_content, history_str
            )
            if session:
                self.active_sessions[user_id] = {
                    "session_type": session,
                    "file_content": file_content
                }
                
        elif intent == "ask_about_existing_information":
            session, response = self.qa_service.handle_query(user_id, query)
            
        elif intent == "assignment":
            session, response = self.assignment_service.handle_assignment(
                user_id, query, history_str
            )
            if session:
                self.active_sessions[user_id] = {
                    "session_type": session,
                    "file_content": None
                }
        else:
            response = "Xin lỗi, tôi không thể xử lý yêu cầu của bạn vào lúc này."

        # Save to memory
        self.memory.add_message(user_id, "user", query)
        self.memory.add_message(user_id, "chatbot", response)
        
        logger.info(f"Response: {response[:100]}")
        return response

    def _route_to_session(
        self,
        user_id: int,
        session_type: str,
        query: str,
        file_content: Optional[str],
        history: str
    ) -> Tuple[Optional[str], str]:
        """Route to appropriate session handler."""
        
        if session_type == "create_new_project":
            return self.project_service.handle_create_project(
                user_id, query, file_content, history
            )
            
        elif session_type in ["update_existing_information", "update_plane_information"]:
            return self.project_service.handle_update_info(
                user_id, query, file_content, history
            )
            
        elif session_type == "assignment":
            return self.assignment_service.handle_assignment(
                user_id, query, history
            )
            
        return None, "Session type không hợp lệ."
