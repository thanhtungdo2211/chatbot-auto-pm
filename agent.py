import os
from memory import RedisMemory
from utils import MemorySelectBot, Router, GenaralBot

from typing import Optional
import logging
from llm.llm_client import LLMClient
from session.session_manager import SessionManager
# Thiết lập cấu hình logging cơ bản
logging.basicConfig(
    level=logging.INFO,                   # Mức log: DEBUG, INFO, WARNING, ERROR, CRITICAL
    format="%(asctime)s [%(levelname)s] %(message)s",  # Format hiển thị
    handlers=[
        logging.StreamHandler(),          # In ra console
        logging.FileHandler("app.log", encoding="utf-8")  # Ghi vào file app.log
    ]
)
class Agent:
    def __init__(self):
        self.short_memory = RedisMemory()
        self.select_memory_bot = MemorySelectBot()
        self.router = Router()
        self.general_bot = GenaralBot()
        self.file_content = None
        self.llm_client = LLMClient()
        self.session_manager = SessionManager(self.llm_client)
        self.session = None 
    def get_short_memory(self, user_id, query):
        history = self.short_memory.get_history(user_id)
        if not history:
            return None
        selected_history = self.select_memory_bot.get_memory_select(history, query)
        return selected_history
        # return str(history)
    def save_to_memory(self, user_id, role, content):
        self.short_memory.add_message(user_id, role, content)
    def query(self,user_id, query = None, file_content = None, long_memory = None):

        logging.info(f"User {user_id} sent a query.")
        logging.info(f"Query: {query}")
        logging.info(f"File content: {file_content}")
        logging.info(f"Long memory: {long_memory}")

        response = "Xin lỗi, tôi không thể xử lý yêu cầu của bạn vào lúc này."
        # Lấy dữ liệu short memory 
        selected_history = self.get_short_memory(user_id, query)

        if file_content is not None and file_content.strip() != "":
            self.file_content = file_content
            return "Tôi đã hoàn tất đọc file. Hiện tại dữ liệu từ file sẽ được lưu để tạo thông tin về project."
        logging.info(f"Current session: {self.session}")
        if self.session is not None:
            self.session, response = self.session_manager.router_session(user_id, self.session, query, self.file_content, selected_history)
            
        else:

            intent = self.router.predict(selected_history, query)

            logging.info(f"Selected history: {selected_history}")
            logging.info(f"Router: {intent}")
            if intent == "other_topics":
                response = self.general_bot.gen_response(selected_history, query)

            elif intent == "create_new_project":
                self.session, response = self.session_manager.router_session(user_id, intent, query, self.file_content, selected_history)
                self.file_content = None
                self.save_to_memory(user_id, "user", query)
                self.save_to_memory(user_id, "chatbot", response)
                return response

            elif intent in ["update_existing_information", "update_plane_information"]:
                self.session, response = self.session_manager.router_session(user_id, intent, query, self.file_content, selected_history)
                self.save_to_memory(user_id, "user", query)
                self.save_to_memory(user_id, "chatbot", response)
                return response

            elif intent == "ask_about_existing_information":
                self.session, response = self.session_manager.router_session(user_id, intent, query, self.file_content, selected_history)
                self.save_to_memory(user_id, "user", query)
                self.save_to_memory(user_id, "chatbot", response)
                return response

            elif intent == "assignment":
                self.session, response = self.session_manager.router_session(user_id, intent, query, self.file_content, selected_history)
                self.save_to_memory(user_id, "user", query)
                self.save_to_memory(user_id, "chatbot", response)
                return response 
        
        self.save_to_memory(user_id, "user", query)
        self.save_to_memory(user_id, "chatbot", response)
        logging.info(f"Response: {response}")   
        return response 