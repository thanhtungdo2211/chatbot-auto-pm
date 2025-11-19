from session.session_create_project.session_create_project import SessionCreateProject
from session.session_update_info import SessionUpdateInfo
from session.session_assignment import SessionAssignment
from session.session_qa import SessionQA

class SessionManager:
    def __init__(self, llm_client):
        self.llm_client = llm_client
        self.session_create_project = SessionCreateProject(llm_client)
        self.session_update_info = SessionUpdateInfo(llm_client)
        self.session_assignment = SessionAssignment(llm_client)
        self.session_qa = SessionQA(llm_client)

    def router_session(self, user_id, intent, query=None, file_content=None, selected_history=None):
        """Route to appropriate session based on intent"""

        if intent == "create_new_project":
            session, response = self.session_create_project.handle_session(
                user_id, query, file_content, selected_history
            )
            return session, response

        elif intent in ["update_existing_information", "update_plane_information"]:
            session, response = self.session_update_info.handle_session(
                user_id, query, file_content, selected_history
            )
            return session, response

        elif intent == "assignment":
            session, response = self.session_assignment.handle_session(
                user_id, query, file_content, selected_history
            )
            return session, response

        elif intent == "ask_about_existing_information":
            session, response = self.session_qa.handle_session(
                user_id, query
            )
            return session, response

        else:
            return None, "Xin lỗi, tôi không hiểu yêu cầu của bạn. Vui lòng thử lại."
