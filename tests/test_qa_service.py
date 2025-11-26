import pytest

from auto_pm_agent_api.application.qa_service.qa_service import QAService


class DummyLLM:
    def __init__(self):
        self.prompts = []

    def generate_response(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return "dummy answer"


class DummyProject:
    def __init__(self):
        self.id = "p1"
        self.name = "Project Alpha"
        self.identifier = "ALPHA"
        self.description = "Alpha desc"
        self.workspace = "ws"


class DummyIssue:
    def __init__(self):
        self.id = "i1"
        self.name = "Issue 1"
        self.description = "Fix bug"
        self.project = "p1"
        self.state = "in progress"
        self.priority = "high"
        self.assignee = "Alice"
        self.start_date = "2024-01-01"
        self.target_date = "2024-02-01"


class DummyMember:
    def __init__(self):
        self.id = "m1"
        self.display_name = "Alice"
        self.email = "alice@example.com"
        self.role = "dev"
        self.member = {"email": self.email}


class DummyPlaneAPI:
    def list_projects(self):
        return [DummyProject()]

    def list_issues(self, project_id=None):
        return [DummyIssue()]

    def list_project_members(self, project_id=None):
        return [DummyMember()]

    def list_members(self):
        return []


class DummyPlaneFactory:
    def __init__(self, api):
        self.api = api

    def get_api(self, user_id=None):
        return self.api


def test_handle_query_returns_llm_response(monkeypatch):
    # Force local TF-IDF backend to avoid external embedding calls
    monkeypatch.setenv("RAG_EMBEDDING_BACKEND", "local")

    llm = DummyLLM()
    plane_api = DummyPlaneAPI()
    service = QAService(llm_client=llm, plane_api_factory=DummyPlaneFactory(plane_api))

    session, response = service.handle_query(123, "Task nào trong Project Alpha?")

    assert session is None
    assert response == "dummy answer"
    assert llm.prompts, "LLM was not invoked"
    prompt = llm.prompts[0]
    assert "Project Alpha" in prompt
    assert "Issue 1" in prompt


def test_handle_query_no_data(monkeypatch):
    monkeypatch.setenv("RAG_EMBEDDING_BACKEND", "local")

    llm = DummyLLM()

    class EmptyPlaneAPI(DummyPlaneAPI):
        def list_projects(self):
            return []

    service = QAService(llm_client=llm, plane_api_factory=DummyPlaneFactory(EmptyPlaneAPI()))

    session, response = service.handle_query(456, "Có dự án nào không?")

    assert session is None
    assert "Không tìm thấy dữ liệu" in response
    assert not llm.prompts, "LLM should not be called when no data is available"
