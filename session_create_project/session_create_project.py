from .plane_extractor import PlaneExtractor
from .check import AffirmativeChecker
from .update_plane import PlaneAPI 
class SessionCreateProject: 
    def __init__(self, llm_client):
        self.api_key_plane = None
        self.worlslug = None

        self.plane_extractor = PlaneExtractor(llm_client)
        self.affirmative_checker = AffirmativeChecker(llm_client)
        
        self.status = None 
        self.result = None 
        self.info = {}
    def check_query(self, query, selected_memory):
        
        return True
    def get_info_plane(self, user_id):
        self.api_key_plane = "plane_api_d958d52c6c0845cb94b8dadd7fef425e"
        self.workslug = "thang"

    def reset_session(self):
        self.status = None 
        self.result = None 
    def handle_session(self, user_id, query, file_content, selected_history):
        if self.api_key_plane is None or self.workslug is None: 
            self.get_info_plane(user_id)
        
        if self.status is None and  (file_content is None or file_content == ""):
            return None, "Vui lòng gửi thông tin để tạo project. Hiện tại dữ liệu về project sẽ được nhận từ file."
        print(self.status)
        if self.status is None: 
            self.result = self.plane_extractor.extract(file_content)
            print("KET QUA EXTRACT PLAN: ", self.result)
            print("IS INFO PROJECT: ", str(self.result.is_info_project).lower())
            if (str(self.result.is_info_project)).lower() == "false":
                return None, "Dữ liệu từ file không hợp lệ. Vui lòng gửi đúng file chứa thông tin về project."
            else: 
                self.status = "ready_to_create_project"
                return "create_new_project", f"Tôi đã trích xuất được thông tin dự án '{self.result.project.name}' với {len(self.result.tasks)} công việc. Bạn có muốn tôi cập nhật dự án lên Plane không?"
        elif self.status == "ready_to_create_project":
            check_affirmative = self.affirmative_checker.check(query)
            print("KET QUA CHECK AFFIRMATIVE: ", check_affirmative)
            if str(check_affirmative.is_affirmative).strip().lower() == "true":
                plane_api = PlaneAPI(self.api_key_plane, self.workslug)
                result = plane_api.upload_project_with_tasks(self.result.project, self.result.tasks)
                self.reset_session()
                return None, f"Dự án đã được tạo thành công! Bạn vào đường dẫn sau: http://192.168.6.16/projects/  với tài khoản là thangtien1411@gmail.com và Thang1411@ để kiểm tra."
            else:
                self.reset_session()
                return None, "Quá trình tạo dự án đã bị hủy. Bạn có yêu cầu gì khác không?"


        # Xử lý logic tạo dự án mới ở đây
        # response = self.llm_client.generate_response(f"Creating new project for user {user_id} with query: {query}")
        # return response