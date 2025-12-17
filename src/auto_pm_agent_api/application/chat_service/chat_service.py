"""Main chat service implementation orchestrating all user interactions."""

import logging
from typing import Optional, Tuple

from auto_pm_agent_api.domain.memory import MemoryInterface
from auto_pm_agent_api.domain.tools import IntentClassifier
from auto_pm_agent_api.application.project_management_service import ProjectManagementService
from auto_pm_agent_api.application.qa_service import QAService
from auto_pm_agent_api.application.assignment_service import AssignmentService
from auto_pm_agent_api.application.report_session import ReportSessionManager

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
        report_manager: ReportSessionManager,
    ):
        self.memory = memory
        self.intent_classifier = intent_classifier
        self.project_service = project_service
        self.qa_service = qa_service
        self.assignment_service = assignment_service
        self.general_bot = general_bot
        self.report_manager = report_manager
        # Map từ Zalo user id -> Plane user id (assignee)
        self.user_id_map = {}
        
        # Track active sessions by user_id
        self.active_sessions = {}

    def handle_query(
        self,
        user_id: int,
        role: str = "manager",
        query: Optional[str] = None,
        file_content: Optional[str] = None,
        mode_report: bool = False,
    ) -> Tuple[str, bool]:
        """
        Handle a user query and return a response with current report mode flag.
        
        Args:
            user_id: User identifier
            role: "manager" | "staff"
            query: User query text
            file_content: Optional file content for project creation
            mode_report: Current report mode flag from client
            
        Returns:
            Tuple of (response string, mode_report flag)
        """
        # Normalize query: if caller sent dict/list, stringify for downstream while keeping payload usable
        raw_query = query
        if query is not None and not isinstance(query, str):
            try:
                import json
                query = json.dumps(query, ensure_ascii=False)
            except Exception:
                query = str(query)
        logger.info(f"User {user_id} [{role}] sent query: {query[:100] if query else 'None'} (mode_report={mode_report})")
        normalized_role = (role or "manager").lower()

        # Handle file upload
        if file_content and file_content.strip():
            self.active_sessions[user_id] = {
                "file_content": file_content,
                "session_type": None
            }
            response = (
                "Tôi đã hoàn tất đọc file. Hiện tại dữ liệu từ file sẽ được lưu để tạo thông tin về project."
            )
            self._save_memory(user_id, query, response)
            return response, mode_report
        
        # Get recent conversation history
        selected_history = self.memory.get_history(user_id, limit=5)
        history_str = selected_history.to_string()

        # Resolve Zalo user id -> Plane user id for staff QA/report
        plane_user_id = self._get_plane_user_id(user_id) if normalized_role == "staff" else str(user_id)
        # Try parse query as JSON payload for staff report context (when mode_report is true)
        extra_staff_payload = None
        if normalized_role == "staff" and mode_report and query:
            extra_staff_payload = self._parse_json_payload(query)
        # Parse manager payload (JSON) when in report mode
        extra_manager_payload = None
        if normalized_role == "manager" and mode_report and query:
            extra_manager_payload = self._parse_json_payload(query)

        # Staff flow: only QA + report logic, no router
        if normalized_role == "staff":
            handled, response, new_mode_report = self.report_manager.handle_staff(
                user_id=user_id,
                role=normalized_role,
                query=query,
                history_str=history_str,
                mode_report_flag=mode_report,
                qa_fallback=lambda: self._handle_staff_qa(user_id, query, history_str, plane_user_id),
                extra_staff_payload=extra_staff_payload,
            )
            if not handled:
                response = self._handle_staff_qa(user_id, query, history_str, plane_user_id)
                new_mode_report = mode_report
            self._save_memory(user_id, query, response)
            return response, new_mode_report

        # Manager flow: handle report-mode specific logic first (non-intrusive)
        handled_report, report_response, current_report_mode = self.report_manager.handle_manager(
            user_id=user_id,
            role=normalized_role,
            query=query,
            history_str=history_str,
            mode_report_flag=mode_report,
            extra_manager_payload=extra_manager_payload,
        )
        if handled_report:
            self._save_memory(user_id, query, report_response)
            return report_response, current_report_mode

        # Check if there's an active session (manager flows)
        active_session = self.active_sessions.get(user_id)

        if active_session and active_session.get("session_type"):
            session, response = self._handle_active_session_flow(
                user_id=user_id,
                query=query,
                history_str=history_str,
                active_session=active_session,
            )

            self._save_memory(user_id, query, response)

            if session is None:
                self.active_sessions.pop(user_id, None)
            else:
                updated = self.active_sessions.get(user_id, active_session)
                updated["session_type"] = session
                self.active_sessions[user_id] = updated

            return response, current_report_mode

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
        self._save_memory(user_id, query, response)
        
        logger.info(f"Response: {response[:100]}")
        return response, current_report_mode

    def _save_memory(self, user_id: int, query: Optional[str], response: str) -> None:
        """Helper to persist conversation messages."""
        try:
            if query is not None:
                self.memory.add_message(user_id, "user", query)
            self.memory.add_message(user_id, "chatbot", response)
        except Exception as exc:
            logger.warning("Could not save conversation history: %s", exc)

    def _parse_json_payload(self, text: Optional[str]) -> Optional[dict]:
        """Try parse JSON string payload; return None if not JSON."""
        if text is None:
            return None
        if isinstance(text, dict):
            return text
        if not isinstance(text, str):
            return None
        import json
        try:
            return json.loads(text)
        except Exception:
            return None

    def _get_plane_user_id(self, user_id: int) -> str:
        """
        Map Zalo user_id -> Plane user id using /api/zalo-users/{zalo_id}.
        Cache results to avoid repeated calls.
        If mapping fails, fall back to original user_id as string.
        """
        uid_str = str(user_id)
        if uid_str in self.user_id_map:
            return self.user_id_map[uid_str]
        plane_user_id = uid_str
        try:
            if hasattr(self.report_manager, "plane_factory") and self.report_manager.plane_factory:
                plane_api = self.report_manager.plane_factory.get_api(user_id)
                user_obj = plane_api.get_user_by_zalo_id(uid_str)
                plane_user_id = user_obj.get("id") or getattr(user_obj, "id", uid_str)
        except Exception as exc:
            logger.warning("Không map được Zalo user_id %s sang Plane id: %s", uid_str, exc)
        self.user_id_map[uid_str] = str(plane_user_id)
        return self.user_id_map[uid_str]

    def _handle_staff_qa(self, user_id: int, query: Optional[str], history_str: str, plane_user_id: Optional[str]) -> str:
        """Route staff QA to issues assigned to them; fallback to general bot for unrelated topics."""
        session, response = self.qa_service.handle_query(
            user_id=user_id,
            query=query or "",
            assignee_filter=str(plane_user_id or user_id),
        )
        # If QA service cannot find data or response is generic, fallback to general bot
        if not response or (
            isinstance(response, str)
            and (
                "Không tìm thấy dữ liệu" in response
                or "không có dữ liệu" in response.lower()
            )
        ):
            return self.general_bot.generate_response(history_str, query)
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

        # If we're waiting for cancellation confirmation, handle it first
        if active_session.get("pending_cancel"):
            return self._handle_cancel_confirmation(
                user_id=user_id,
                query=query,
                history_str=history_str,
                active_session=active_session,
            )

        # If user replies with a pure confirmation token, keep routing to current session
        if self._is_confirmation_token(query):
            file_content = active_session.get("file_content")
            session, response = self._route_to_session(
                user_id, session_type, query, file_content, history_str
            )
            return session, response

        intent_result = self.intent_classifier.classify(history_str, query)
        new_intent = intent_result.intent

        if self._is_intent_compatible(session_type, new_intent):
            # Allow informational QA during an active flow without resetting the session
            if new_intent == "ask_about_existing_information":
                session, response = self.qa_service.handle_query(user_id, query)
                reminder = self._build_active_session_reminder(
                    session_type=session_type, user_id=user_id, active_session=active_session
                )
                if reminder:
                    response = f"{response}\n\n{reminder}"
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
            message = self._build_continue_message(
                session_type=active_session.get("session_type"),
                user_id=user_id,
                active_session=active_session,
            )
            return active_session.get("session_type"), message

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

    def _build_continue_message(
        self, session_type: Optional[str], user_id: int, active_session: dict
    ) -> str:
        """
        Provide a contextual continue message after user chọn 'không' (không hủy).
        If create_new_project đang chờ confirm, nhắc lại prompt trước.
        """
        prefix = f"Ok, tiếp tục luồng '{session_type}'. "

        if session_type == "create_new_project":
            # Thử lấy dữ liệu trích xuất để nhắc lại prompt xác nhận
            project_session = getattr(self.project_service, "sessions", {}).get(user_id, {})
            extracted = project_session.get("extracted_data")
            project = getattr(extracted, "project", None) if extracted else None
            project_name = getattr(project, "name", None)
            tasks = getattr(extracted, "tasks", None) if extracted else None
            task_count = len(tasks) if tasks else 0
            if project_name:
                return (
                    prefix
                    + f"Tôi đã trích xuất được thông tin dự án '{project_name}' với {task_count} công việc. "
                    "Bạn có muốn tôi cập nhật dự án lên Plane không?"
                )

        if session_type == "update_existing_information":
            summary = ""
            try:
                summary = self.project_service.summarize_update_session(user_id)
            except Exception:
                summary = ""
            if summary:
                return f"{prefix}{summary}"

        # Fallback chung cho các luồng khác
        return (
            prefix
            + "Vui lòng trả lời tiếp nội dung bot vừa hỏi trong luồng này (ví dụ: xác nhận hoặc bổ sung thông tin)."
        )

    def _build_active_session_reminder(
        self, session_type: Optional[str], user_id: int, active_session: dict
    ) -> str:
        """
        Khi user hỏi thông tin (QA) trong lúc đang có session khác,
        nhắc lại context đang chờ để tránh quên bước confirm.
        """
        if session_type == "create_new_project":
            project_session = getattr(self.project_service, "sessions", {}).get(user_id, {})
            extracted = project_session.get("extracted_data")
            status = project_session.get("status")
            project = getattr(extracted, "project", None) if extracted else None
            project_name = getattr(project, "name", None)
            tasks = getattr(extracted, "tasks", None) if extracted else None
            task_count = len(tasks) if tasks else 0
            if status == "ready_to_create" and project_name:
                return (
                    f"Lưu ý: bạn vẫn đang ở luồng tạo project. "
                    f"Tôi đã trích xuất được dự án '{project_name}' với {task_count} công việc. "
                    "Bạn có muốn tôi cập nhật dự án lên Plane không?"
                )
        elif session_type == "update_existing_information":
            summary = ""
            try:
                summary = self.project_service.summarize_update_session(user_id)
            except Exception:
                summary = ""
            if summary:
                return f"Lưu ý: bạn vẫn đang ở luồng cập nhật. {summary}"
        return ""

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

