import pytest

from auto_pm_agent_api.application.project_management_service.project_management_service import (
    ProjectManagementService,
    UpdateExtractResult,
)


class DummyPlaneProject:
    def __init__(self, project_id: str, name: str, identifier: str):
        self.id = project_id
        self.name = name
        self.identifier = identifier


class DummyIssue:
    def __init__(self, issue_id: str, name: str, assignee=None):
        self.id = issue_id
        self.name = name
        self.assignee = assignee


class DummyPlaneAPI:
    def __init__(self):
        self.add_member_calls = []
        self.projects = [
            DummyPlaneProject("proj-1", "Demo Project", "DEMO"),
        ]
        self.issues = {"proj-1": [DummyIssue("task-1", "Task A", None)]}
        self.update_project_calls = []
        self.update_issue_calls = []
        self.create_issue_calls = []
        self.delete_issue_calls = []
        self.members = [
            {"id": "m1", "email": "alice@example.com", "display_name": "Alice"},
            {"id": "m2", "email": "newuser10@example.com", "display_name": "New User"},
        ]

    def list_projects(self):
        return self.projects

    def add_member_to_project(self, project_id: str, email: str, role: int):
        self.add_member_calls.append(
            {"project_id": project_id, "email": email, "role": role}
        )
        return {"status": "ok"}

    def update_project(self, project_id: str, **kwargs):
        self.update_project_calls.append({"project_id": project_id, **kwargs})
        return {"status": "ok"}

    def delete_project(self, project_id: str):
        return True

    def list_members(self):
        return [member for member in self.members]

    def list_issues(self, project_id: str):
        return self.issues.get(project_id, [])

    def update_issue(self, project_id: str, issue_id: str, **kwargs):
        self.update_issue_calls.append({"project_id": project_id, "issue_id": issue_id, **kwargs})
        return {"status": "ok"}

    def create_issue(self, project_id: str, name: str, description: str = "", **kwargs):
        self.create_issue_calls.append({"project_id": project_id, "name": name, "description": description})
        return {"status": "ok"}

    def delete_issue(self, project_id: str, issue_id: str):
        self.delete_issue_calls.append({"project_id": project_id, "issue_id": issue_id})
        return True


class DummyPlaneFactory:
    def __init__(self, api: DummyPlaneAPI):
        self.api = api

    def get_api(self, user_id=None):
        return self.api


class DummyLLM:
    def __init__(self, result: UpdateExtractResult):
        self.result = result
        self.last_prompt = None

    def generate_response(self, prompt, output_format=None):
        self.last_prompt = prompt
        return self.result


def test_handle_update_info_add_member_flow():
    """Ensure add_member flow extracts info and calls Plane API on confirmation."""
    plane_api = DummyPlaneAPI()
    llm_result = UpdateExtractResult(action_type="add_member", project="Demo Project")
    llm = DummyLLM(result=llm_result)
    service = ProjectManagementService(llm, DummyPlaneFactory(plane_api))

    # Step 1: ask to add member
    state, message = service.handle_update_info(
        user_id=1,
        query="Thêm alice@example.com vào project Demo Project",
        file_content=None,
        history="",
    )
    assert state == "update_existing_information"
    assert "alice@example.com" in message
    assert "Demo Project" in message

    # Step 2: confirm
    state2, message2 = service.handle_update_info(
        user_id=1,
        query="có",
        file_content=None,
        history="",
    )
    assert state2 is None
    assert "Đã thêm member" in message2
    assert plane_api.add_member_calls, "Plane API add_member_to_project was not called"
    call = plane_api.add_member_calls[0]
    assert call["email"] == "alice@example.com"
    assert call["project_id"] == "proj-1"
    assert call["role"] == 15


def test_handle_update_info_remove_member_flow_with_uuid():
    """Ensure remove_member uses UUID from LLM and calls Plane API."""
    plane_api = DummyPlaneAPI()
    plane_api.list_members = lambda: []  # no need to resolve email
    llm_result = UpdateExtractResult(
        action_type="remove_member",
        member_id="83d66dd9-9775-4178-ac4b-b7cdd9c7593d",
    )
    llm = DummyLLM(result=llm_result)
    # add remove tracking
    plane_api.remove_member_calls = []
    def _remove(member_id):
        plane_api.remove_member_calls.append(member_id)
        return True
    plane_api.remove_member_from_workspace = _remove

    service = ProjectManagementService(llm, DummyPlaneFactory(plane_api))

    state, message = service.handle_update_info(
        user_id=1,
        query="Xóa member 83d66dd9-9775-4178-ac4b-b7cdd9c7593d khỏi project",
        file_content=None,
        history="",
    )
    assert state == "update_existing_information"
    assert "83d66dd9-9775-4178-ac4b-b7cdd9c7593d" in message

    state2, message2 = service.handle_update_info(
        user_id=1,
        query="có",
        file_content=None,
        history="",
    )
    assert state2 is None
    assert plane_api.remove_member_calls == ["83d66dd9-9775-4178-ac4b-b7cdd9c7593d"]
    assert "Đã xóa member" in message2


def test_handle_update_info_update_project_flow():
    """Ensure update_project flow updates the project field."""
    plane_api = DummyPlaneAPI()
    llm_result = UpdateExtractResult(
        action_type="update_project",
        project_name="Demo Project",
        field="description",
        value="New desc",
    )
    llm = DummyLLM(result=llm_result)
    service = ProjectManagementService(llm, DummyPlaneFactory(plane_api))

    state, msg = service.handle_update_info(
        user_id=1,
        query="Cập nhật mô tả dự án Demo Project",
        file_content=None,
        history="",
    )
    assert state == "update_existing_information"
    assert "Demo Project" in msg

    state2, msg2 = service.handle_update_info(
        user_id=1,
        query="có",
        file_content=None,
        history="",
    )
    assert state2 is None
    assert plane_api.update_project_calls
    call = plane_api.update_project_calls[0]
    assert call["project_id"] == "proj-1"
    assert call["description"] == "New desc"


def test_handle_update_info_update_task_flow():
    """Ensure update_task flow updates issue via Plane API."""
    plane_api = DummyPlaneAPI()
    llm_result = UpdateExtractResult(
        action_type="update_task",
        project_name="Demo Project",
        task_name="Task A",
        field="priority",
        value="high",
    )
    llm = DummyLLM(result=llm_result)
    service = ProjectManagementService(llm, DummyPlaneFactory(plane_api))

    state, msg = service.handle_update_info(
        user_id=1,
        query="Đổi priority Task A trong Demo Project",
        file_content=None,
        history="",
    )
    assert state == "update_existing_information"
    assert "Task A" in msg

    state2, msg2 = service.handle_update_info(
        user_id=1,
        query="có",
        file_content=None,
        history="",
    )
    assert state2 is None
    assert plane_api.update_issue_calls
    call = plane_api.update_issue_calls[0]
    assert call["project_id"] == "proj-1"
    assert call["issue_id"] == "task-1"
    assert call["priority"] == "high"
