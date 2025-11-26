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
    https://skillbuilder.aws/
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
            session, response = self._handle_active_session_flow(
                user_id=user_id,
                query=query,
                history_str=history_str,
                active_session=active_session,
            )

            self.memory.add_message(user_id, "user", query)
            self.memory.add_message(user_id, "chatbot", response)

            if session is None:
                self.active_sessions.pop(user_id, None)
            else:
                updated = self.active_sessions.get(user_id, active_session)
                updated["session_type"] = session
                self.active_sessions[user_id] = updated

            return response

        # No active session - classify intent
        intent_result = self.intent_classifier.classify(history_str, query)
        intent = intent_result.intent
        intent = self._apply_intent_overrides(intent, query)
        
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

    def _apply_intent_overrides(self, intent: str, query: str) -> str:
        """
        Heuristics to correct intent classification for certain patterns.
        
        - Requests to add/remove members should be treated as update_existing_information
          (not assignment), even if the classifier mislabels.
        """
        q_lower = (query or "").lower()
        member_keywords = ["add member", "thêm member", "thêm thành viên", "add user", "thêm user"]
        remove_keywords = ["remove member", "xóa member", "xoa member", "remove user", "xóa thành viên"]
        has_member_action = any(kw in q_lower for kw in member_keywords + remove_keywords)
        has_project = "project" in q_lower or "dự án" in q_lower

        if has_member_action and has_project:
            return "update_existing_information"

        return intent

    def _handle_active_session_flow(
        self,
        user_id: int,
        query: str,
        history_str: str,
        active_session: dict,
    ) -> Tuple[Optional[str], str]:
        """Handle messages when a session is already in progress."""
        session_type = active_session.get("session_type")

        # If user replies with a pure confirmation token, keep routing to current session
        if self._is_confirmation_token(query):
            file_content = active_session.get("file_content")
            session, response = self._route_to_session(
                user_id, session_type, query, file_content, history_str
            )
            return session, response

        # If we're waiting for cancellation confirmation, handle it first
        if active_session.get("pending_cancel"):
            return self._handle_cancel_confirmation(
                user_id=user_id,
                query=query,
                history_str=history_str,
                active_session=active_session,
            )

        intent_result = self.intent_classifier.classify(history_str, query)
        new_intent = intent_result.intent

        if self._is_intent_compatible(session_type, new_intent):
            # Allow informational QA during an active flow without resetting the session
            if new_intent == "ask_about_existing_information":
                session, response = self.qa_service.handle_query(user_id, query)
                return session_type, response

            # Continue the current session as normal
            file_content = active_session.get("file_content")
            session, response = self._route_to_session(
                user_id, session_type, query, file_content, history_str
            )
            return session or session_type, response

        # Different or unrelated intent → ask for confirmation to cancel current flow
        active_session.update(
            {
                "pending_cancel": True,
                "pending_intent": new_intent,
                "pending_query": query,
                "pending_history": history_str,
            }
        )
        self.active_sessions[user_id] = active_session
        response = self._build_cancel_prompt(session_type, new_intent)
        return session_type, response

    def _handle_cancel_confirmation(
        self,
        user_id: int,
        query: str,
        history_str: str,
        active_session: dict,
    ) -> Tuple[Optional[str], str]:
        """Process yes/no confirmation when user tries to switch flows mid-session."""
        normalized = (query or "").strip().lower()
        yes_tokens = {"yes", "y", "có", "co", "ok", "oke", "đồng ý", "hủy", "cancel", "do it"}
        no_tokens = {"no", "n", "không", "ko", "k", "khong", "tiếp", "tiếp tục", "continue"}

        if normalized in yes_tokens:
            pending_intent = active_session.get("pending_intent") or "other_topics"
            pending_query = active_session.get("pending_query") or query
            self.active_sessions.pop(user_id, None)
            return self._execute_intent(
                user_id=user_id,
                intent=pending_intent,
                query=pending_query,
                history_str=history_str,
                file_content=None,
            )

        if normalized in no_tokens:
            active_session.pop("pending_cancel", None)
            active_session.pop("pending_intent", None)
            active_session.pop("pending_query", None)
            active_session.pop("pending_history", None)
            self.active_sessions[user_id] = active_session
            return active_session.get("session_type"), (
                "Ok, tiếp tục luồng hiện tại. Vui lòng cung cấp bước tiếp theo."
            )

        # Ask again if unclear
        return active_session.get("session_type"), (
            "Bạn muốn hủy luồng hiện tại để chuyển sang yêu cầu mới? "
            "Trả lời 'có' để hủy, 'không' để tiếp tục."
        )

    def _is_intent_compatible(self, current_session: str, new_intent: str) -> bool:
        """Check if a new intent can be handled within the current flow."""
        if not current_session:
            return True
        if new_intent == current_session:
            return True
        # Allow asking about existing information during any active flow
        if new_intent == "ask_about_existing_information":
            return True
        return False

    def _build_cancel_prompt(self, current_session: str, new_intent: str) -> str:
        """Prompt user to confirm canceling the current flow."""
        return (
            f"Bạn đang thực hiện luồng '{current_session}'. "
            f"Bạn muốn hủy để chuyển sang yêu cầu '{new_intent}' không? "
            "Trả lời 'có' để hủy và chuyển, 'không' để tiếp tục luồng hiện tại."
        )

    def _is_confirmation_token(self, query: str) -> bool:
        """Check if user input is a bare confirmation (yes/no) to continue current flow."""
        normalized = (query or "").strip().lower()
        yes_tokens = {"yes", "y", "có", "co", "ok", "oke", "đồng ý"}
        no_tokens = {"no", "n", "không", "ko", "k", "khong"}
        return normalized in yes_tokens or normalized in no_tokens

    def _execute_intent(
        self,
        user_id: int,
        intent: str,
        query: str,
        history_str: str,
        file_content: Optional[str],
    ) -> Tuple[Optional[str], str]:
        """Route execution for a new intent (used after cancellation)."""
        if intent == "other_topics":
            response = self.general_bot.generate_response(history_str, query)
            return None, response

        if intent in ["create_new_project", "update_existing_information", "update_plane_information"]:
            session, response = self._route_to_session(
                user_id, intent, query, file_content, history_str
            )
            if session:
                self.active_sessions[user_id] = {
                    "session_type": session,
                    "file_content": file_content,
                }
            return session, response

        if intent == "ask_about_existing_information":
            session, response = self.qa_service.handle_query(user_id, query)
            return session, response

        if intent == "assignment":
            session, response = self.assignment_service.handle_assignment(
                user_id, query, history_str
            )
            if session:
                self.active_sessions[user_id] = {
                    "session_type": session,
                    "file_content": None,
                }
            return session, response

        response = "Xin lỗi, tôi không thể xử lý yêu cầu của bạn vào lúc này."
        return None, response
