# import requests
# import re
# from typing import List
# from pydantic import BaseModel, Field
# from dotenv import load_dotenv
# import os
# load_dotenv()

# BASE_URL_PLANE = os.getenv("BASE_URL_PLANE") or "https://api.plane.so"

# # ===============================
# # 🎯 SCHEMA DỮ LIỆU (dùng Pydantic)
# # ===============================
# class TaskSchema(BaseModel):
#     name: str = Field(..., description="Tên công việc (task name)")
#     description: str | None = Field(None, description="Mô tả hoặc kết quả task")
#     start_date: str | None = Field(None, description="Ngày bắt đầu (YYYY-MM-DD)")
#     target_date: str | None = Field(None, description="Ngày kết thúc (YYYY-MM-DD)")

# class ProjectSchema(BaseModel):
#     name: str
#     identifier: str
#     description: str | None = None


# # ===============================
# # 🧠 CLASS CHÍNH DUY NHẤT: PlaneAPI
# # ===============================
# class PlaneAPI:
#     def __init__(self, api_key: str, workspace_slug: str):
#         self.api_key = api_key
#         self.workspace_slug = workspace_slug
#         self.base_url = f"{BASE_URL_PLANE}/api/v1/workspaces/{workspace_slug}"
#         self.headers = {
#             "x-api-key": api_key,
#             "Content-Type": "application/json"
#         }

#     # ------------------------------
#     # 🧩 1. Tạo Project mới
#     # ------------------------------
#     def create_project(self, name: str, identifier: str, description: str = ""):
#         """
#         Tạo project mới trong Plane
#         """
#         url = f"{self.base_url}/projects/"
#         payload = {
#             "name": name,
#             "identifier": re.sub(r"[^A-Z]", "", identifier.upper())[:6],
#             "description": description or "",
#             "network": 2,
#             "is_deployed":True,
#         }
#         res = requests.post(url, json=payload, headers=self.headers)
#         if res.status_code in (200, 201):
#             data = res.json()
#             print(f"✅ Tạo Project thành công: {data.get('name')} ({data.get('id')})")
#             return data
#         else:
#             print(f"❌ Lỗi tạo Project: {res.status_code} - {res.text}")
#             return None

#     # ------------------------------
#     # 🧩 2. Tạo Task (Issue)
#     # ------------------------------
#     def create_task(self, project_id: str, task: TaskSchema):
#         """
#         Tạo task (issue) trong Plane
#         """
#         url = f"{self.base_url}/projects/{project_id}/issues/"
#         payload = {
#             "name": task.name,
#             "description": task.description or "",
#             "start_date": task.start_date,
#             "target_date": task.target_date,
#         }
#         res = requests.post(url, json=payload, headers=self.headers)
#         if res.status_code in (200, 201):
#             print(f"🧩 Tạo Task: {task.name}")
#             return res.json()
#         else:
#             print(f"❌ Lỗi tạo Task {task.name}: {res.status_code} - {res.text}")
#             return None

#     # ------------------------------
#     # 🚀 3. Upload toàn bộ Project + Tasks
#     # ------------------------------
#     def upload_project_with_tasks(self, project: ProjectSchema, tasks: List[TaskSchema]):
#         """
#         Tự động tạo Project và toàn bộ danh sách Task trong Plane
#         """
#         # --- Tạo project ---
#         project_data = self.create_project(
#             name=project.name,
#             identifier=project.identifier,
#             description=project.description or ""
#         )

#         if not project_data:
#             return "❌ Không thể tạo project"

#         project_id = project_data.get("id")

#         # --- Tạo các task ---
#         for t in tasks:
#             self.create_task(project_id, t)
#         return f"✅ Đã tạo project '{project.name}' và {len(tasks)} task thành công. Truy cập vào URL sau để xem Project: https://app.plane.so/{self.workspace_slug}/projects/{project_id}/issues/"
#     def get_projects(self):
#         url = f"{self.base_url}/projects/"
#         res = requests.get(url, headers=self.headers)
#         if res.status_code == 200:
#             data = res.json()
#             return data["results"] if isinstance(data, dict) else data
#         return []
#     def get_issues(self, project_id: str):
#         url = f"{self.base_url}/projects/{project_id}/issues/"
#         res = requests.get(url, headers=self.headers)
#         if res.status_code == 200:
#             data = res.json()
#             return data["results"] if isinstance(data, dict) else data
#         return []
#     def get_project_members(self, project_id: str):
#         url = f"{self.base_url}/projects/{project_id}/members/"
#         res = requests.get(url, headers=self.headers)
#         if res.status_code == 200:
#             data = res.json()
#             if isinstance(data, list):
#                 return data
#             return data.get("results", [])
#         return []
#     def find_project_by_name(self, name: str):
#         name = name.lower()
#         for p in self.get_projects():
#             if name in p.get("name", "").lower():
#                 return p
#         return None
#     def find_issue_by_name(self, project_id: str, name: str):
#         name = name.lower()
#         for issue in self.get_issues(project_id):
#             if name in issue.get("name", "").lower():
#                 return issue
#         return None
#     def get_member_workload(self, project_id: str):
#         issues = self.get_issues(project_id)
#         members = self.get_project_members(project_id)

#         workload = {}

#         # Khởi tạo
#         for m in members:
#             mid = m.get("member", {}).get("id")
#             name = m.get("member", {}).get("display_name", "Unknown")
#             workload[mid] = {"name": name, "count": 0, "tasks": []}

#         # Đếm task
#         for issue in issues:
#             for uid in issue.get("assignees", []):
#                 if uid in workload:
#                     workload[uid]["count"] += 1
#                     workload[uid]["tasks"].append(issue.get("name"))

#         return workload
#         # ------------------------------
#     # 👥  NEW: Lấy danh sách MEMBERS trong workspace
#     # ------------------------------
#     def get_workspace_members(self):
#         """
#         Lấy toàn bộ danh sách members trong workspace.
#         API: GET /api/v1/workspaces/{workspace_slug}/members/
#         """
#         url = f"{BASE_URL_PLANE}/api/v1/workspaces/{self.workspace_slug}/members/"
#         res = requests.get(url, headers=self.headers)

#         if res.status_code != 200:
#             print(f"❌ Lỗi lấy workspace members: {res.status_code} - {res.text}")
#             return []

#         data = res.json()

#         # Plane API thường trả LIST trực tiếp
#         if isinstance(data, list):
#             return data

#         # Nếu trả dict → fallback
#         return data.get("results", [])

#     def get_all_data_for_rag(self):
#         all_data = []

#         projects = self.get_projects()

#         for p in projects:
#             pid = p.get("id")
#             pname = p.get("name")

#             all_data.append({
#                 "type": "project",
#                 "id": pid,
#                 "name": pname,
#                 "description": p.get("description", "")
#             })

#             # Issues
#             issues = self.get_issues(pid)
#             for issue in issues:
#                 state_obj = issue.get("state_detail") or issue.get("state") or {}
#                 all_data.append({
#                     "type": "issue",
#                     "id": issue.get("id"),
#                     "name": issue.get("name"),
#                     "project_name": pname,
#                     "description": issue.get("description_stripped"),
#                     "priority": issue.get("priority"),
#                     "start_date": issue.get("start_date"),
#                     "target_date": issue.get("target_date"),
#                     "assignees": issue.get("assignees", [])
#                 })

#             # Members
#             members = self.get_project_members(pid)
#             for m in members:
#                 info = m.get("member", {})
#                 all_data.append({
#                     "type": "member",
#                     "project_name": pname,
#                     "name": info.get("display_name"),
#                     "email": info.get("email"),
#                     "role": m.get("role", "none")
#                 })
#             members_workspace = self.get_workspace_members()
#             for m in members_workspace:
#                 all_data.append({
#                     "type": "member",
#                     "project_name": "workspace",
#                     "name": m.get("display_name"),
#                     "email": m.get("email"),
#                     "role": m.get("role", "none")
#                 })

#         return all_data
    
#     def update_issue(self, project_id, issue_id, update_data):
#         """
#         Cập nhật thông tin một issue (task) trong Plane
#         """
#         url = f"{self.base_url}/projects/{project_id}/issues/{issue_id}/"
#         res = requests.patch(url, json=update_data, headers=self.headers)
#         if res.status_code in (200, 204):
#             print(f"✅ Cập nhật Issue {issue_id} thành công.")
#             return res.json()
#         else:
#             print(f"❌ Lỗi cập nhật Issue {issue_id}: {res.status_code} - {res.text}")
#             return None

#     def update_project(self, project_id: str, update_data: dict):
#         """
#         Cập nhật thông tin project trên Plane.
#         URL: PATCH /projects/{project_id}/
#         """
#         url = f"{self.base_url}/projects/{project_id}/"

#         try:
#             response = requests.patch(url, json=update_data, headers=self.headers)

#             if response.status_code in (200, 202):
#                 print("[PlaneAPI] Project updated:", response.json())
#                 return response.json()
#             else:
#                 print(f"[PlaneAPI] Failed to update project: HTTP {response.status_code}")
#                 print(response.text)
#                 return None

#         except Exception as e:
#             print("[PlaneAPI] Exception updating project:", str(e))
#             return None

# # if __name__ == "__main__":
# #     api_key = "plane_api_21dc890911434c478b91e523fc46349f"
# #     workspace_slug = "mtagi"

# #     plane = PlaneAPI(api_key, workspace_slug)

# #     # Tạo project
# #     project = ProjectSchema(
# #         name="Nhận diện khuôn mặt Spa",
# #         identifier="NVDKMS",
# #         description="Dự án phát triển hệ thống nhận diện khuôn mặt cho Spa"
# #     )

# #     # Danh sách task
# #     tasks = [
# #         TaskSchema(
# #             name="Nghiên cứu về Gstream, DeepStream",
# #             description="Hoàn thiện",
# #             start_date="2025-02-03",
# #             target_date="2025-02-07",
# #             assignees=["Duy", "Quang"]
# #         ),
# #         TaskSchema(
# #             name="Xây dựng Base Pipeline chạy trên camera với file config",
# #             description="Hoàn thiện",
# #             start_date="2025-02-10",
# #             target_date="2025-02-14",
# #             assignees=["Duy"]
# #         ),
# #     ]

# #     # Gọi hàm upload toàn bộ
# #     result = plane.upload_project_with_tasks(project, tasks)
# #     print(result)

import requests
import re
from typing import List
from pydantic import BaseModel, Field
from dotenv import load_dotenv
import os

load_dotenv()

BASE_URL_PLANE = os.getenv("BASE_URL_PLANE") or "https://api.plane.so"


# ======================================================
# 🧩 SCHEMA DỮ LIỆU
# ======================================================

class TaskSchema(BaseModel):
    name: str
    description: str | None = None
    start_date: str | None = None
    target_date: str | None = None


class ProjectSchema(BaseModel):
    name: str
    identifier: str
    description: str | None = None


# ======================================================
# 🧠 CLASS CHÍNH: PlaneAPI
# ======================================================

class PlaneAPI:
    def __init__(self, api_key: str, workspace_slug: str):
        self.api_key = api_key
        self.workspace_slug = workspace_slug
        self.base_url = f"{BASE_URL_PLANE}/api/v1/workspaces/{workspace_slug}"
        self.headers = {
            "x-api-key": api_key,
            "Content-Type": "application/json"
        }

    # ==================================================
    # 🚀 1. PROJECT CRUD
    # ==================================================

    def create_project(self, name: str, identifier: str, description: str = ""):
        url = f"{self.base_url}/projects/"
        payload = {
            "name": name,
            "identifier": re.sub(r"[^A-Z]", "", identifier.upper())[:6],
            "description": description or "",
            "network": 2,
            "is_deployed": True,
        }
        res = requests.post(url, json=payload, headers=self.headers)
        if res.status_code in (200, 201):
            data = res.json()
            print(f"✅ Created Project: {data.get('name')}")
            return data
        print(f"❌ Create Project Failed: {res.status_code} - {res.text}")
        return None
    def upload_project_with_tasks(self, project: ProjectSchema, tasks: List[TaskSchema]):
        """
        Tự động tạo Project và toàn bộ danh sách Task trong Plane
        """
        # --- Tạo project ---
        project_data = self.create_project(
            name=project.name,
            identifier=project.identifier,
            description=project.description or ""
        )

        if not project_data:
            return "❌ Không thể tạo project"

        project_id = project_data.get("id")

        # --- Tạo các task ---
        for t in tasks:
            self.create_task(project_id, t)
        return f"✅ Đã tạo project '{project.name}' và {len(tasks)} task thành công. Truy cập vào URL sau để xem Project: https://app.plane.so/{self.workspace_slug}/projects/{project_id}/issues/"
    def update_project(self, project_id: str, update_data: dict):
        url = f"{self.base_url}/projects/{project_id}/"
        res = requests.patch(url, json=update_data, headers=self.headers)
        if res.status_code in (200, 202):
            return res.json()
        print(f"❌ Update Project Failed: {res.status_code} - {res.text}")
        return None

    def delete_project(self, project_id: str):
        url = f"{self.base_url}/projects/{project_id}/"
        res = requests.delete(url, headers=self.headers)
        if res.status_code in (200, 204):
            print(f"🗑️ Deleted Project {project_id}")
            return True
        print(f"❌ Delete Project Failed: {res.status_code} - {res.text}")
        return False

    def get_project_detail(self, project_id: str):
        url = f"{self.base_url}/projects/{project_id}/"
        res = requests.get(url, headers=self.headers)
        if res.status_code == 200:
            return res.json()
        print(f"❌ Get Project Detail Failed: {res.status_code} - {res.text}")
        return None

    def get_projects(self):
        url = f"{self.base_url}/projects/"
        res = requests.get(url, headers=self.headers)
        if res.status_code == 200:
            data = res.json()
            return data["results"] if isinstance(data, dict) else data
        return []

    def find_project_by_name(self, name: str):
        name = name.lower()
        for p in self.get_projects():
            if name in p.get("name", "").lower():
                return p
        return None

    # ==================================================
    # 🚀 2. TASK CRUD (Issue)
    # ==================================================

    def create_task(self, project_id: str, task: TaskSchema):
        url = f"{self.base_url}/projects/{project_id}/issues/"
        payload = {
            "name": task.name,
            "description": task.description or "",
            "start_date": task.start_date,
            "target_date": task.target_date,
        }
        res = requests.post(url, json=payload, headers=self.headers)
        if res.status_code in (200, 201):
            return res.json()
        print(f"❌ Create Task Failed: {res.status_code} - {res.text}")
        return None

    def update_issue(self, project_id: str, issue_id: str, update_data: dict):
        url = f"{self.base_url}/projects/{project_id}/issues/{issue_id}/"
        res = requests.patch(url, json=update_data, headers=self.headers)
        if res.status_code in (200, 204):
            return res.json()
        print(f"❌ Update Issue Failed: {res.status_code} - {res.text}")
        return None

    def delete_issue(self, project_id: str, issue_id: str):
        url = f"{self.base_url}/projects/{project_id}/issues/{issue_id}/"
        res = requests.delete(url, headers=self.headers)
        if res.status_code in (200, 204):
            print(f"🗑️ Deleted Issue {issue_id}")
            return True
        print(f"❌ Delete Issue Failed: {res.status_code} - {res.text}")
        return False

    def get_issue_detail(self, project_id: str, issue_id: str):
        url = f"{self.base_url}/projects/{project_id}/issues/{issue_id}/"
        res = requests.get(url, headers=self.headers)
        if res.status_code == 200:
            return res.json()
        print(f"❌ Get Issue Detail Failed: {res.status_code} - {res.text}")
        return None

    def get_issues(self, project_id: str):
        url = f"{self.base_url}/projects/{project_id}/issues/"
        res = requests.get(url, headers=self.headers)
        if res.status_code == 200:
            data = res.json()
            return data["results"] if isinstance(data, dict) else data
        return []

    def find_issue_by_name(self, project_id: str, name: str):
        name = name.lower()
        for issue in self.get_issues(project_id):
            if name in issue.get("name", "").lower():
                return issue
        return None

    # ==================================================
    # 🚀 3. TASK UTILITIES
    # ==================================================

    def assign_task(self, project_id: str, issue_id: str, member_ids: List[str]):
        url = f"{self.base_url}/projects/{project_id}/issues/{issue_id}/"
        payload = {"assignees": member_ids}
        res = requests.patch(url, json=payload, headers=self.headers)
        if res.status_code in (200, 204):
            return res.json()
        print(f"❌ Assign Task Failed: {res.status_code} - {res.text}")
        return None

    def update_issue_state(self, project_id: str, issue_id: str, state_id: str):
        url = f"{self.base_url}/projects/{project_id}/issues/{issue_id}/"
        payload = {"state": state_id}
        res = requests.patch(url, json=payload, headers=self.headers)
        if res.status_code in (200, 204):
            return res.json()
        print(f"❌ Update State Failed: {res.status_code} - {res.text}")
        return None

    def update_issue_priority(self, project_id: str, issue_id: str, priority: str):
        url = f"{self.base_url}/projects/{project_id}/issues/{issue_id}/"
        payload = {"priority": priority}
        res = requests.patch(url, json=payload, headers=self.headers)
        if res.status_code in (200, 204):
            return res.json()
        print(f"❌ Update Priority Failed: {res.status_code} - {res.text}")
        return None

    # ==================================================
    # 🚀 4. MEMBER & RAG DATA
    # ==================================================

    def get_project_members(self, project_id: str):
        url = f"{self.base_url}/projects/{project_id}/members/"
        res = requests.get(url, headers=self.headers)
        if res.status_code == 200:
            data = res.json()
            return data if isinstance(data, list) else data.get("results", [])
        return []

    def get_workspace_members(self):
        url = f"{BASE_URL_PLANE}/api/v1/workspaces/{self.workspace_slug}/members/"
        res = requests.get(url, headers=self.headers)
        if res.status_code == 200:
            data = res.json()
            return data if isinstance(data, list) else data.get("results", [])
        return []

    def get_member_workload(self, project_id: str):
        issues = self.get_issues(project_id)
        members = self.get_project_members(project_id)

        workload = {
            m["member"]["id"]: {
                "name": m["member"]["display_name"],
                "count": 0,
                "tasks": []
            }
            for m in members
        }

        for issue in issues:
            for uid in issue.get("assignees", []):
                if uid in workload:
                    workload[uid]["count"] += 1
                    workload[uid]["tasks"].append(issue["name"])

        return workload

    def get_all_data_for_rag(self):
        all_data = []
        projects = self.get_projects()

        for p in projects:
            pid = p["id"]
            pname = p.get("name")

            all_data.append({
                "type": "project",
                "id": pid,
                "name": pname,
                "description": p.get("description", "")
            })

            for issue in self.get_issues(pid):
                all_data.append({
                    "type": "issue",
                    "id": issue.get("id"),
                    "name": issue.get("name"),
                    "project_name": pname,
                    "description": issue.get("description_stripped"),
                    "priority": issue.get("priority"),
                    "start_date": issue.get("start_date"),
                    "target_date": issue.get("target_date"),
                    "assignees": issue.get("assignees", [])
                })

            for m in self.get_project_members(pid):
                info = m.get("member", {})
                all_data.append({
                    "type": "member",
                    "project_name": pname,
                    "name": info.get("display_name"),
                    "email": info.get("email"),
                    "role": m.get("role", "none")
                })

        return all_data
