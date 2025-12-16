import pytest
from fastapi.testclient import TestClient

from auto_pm_agent_api.domain.models import DailyTask, DailyTasks, WorkReportData
from auto_pm_agent_api.infrastructure.api import main


class DummyChatService:
    def __init__(self, response="ok", raise_on_chat=False, raise_on_clear=False):
        self.response = response
        self.raise_on_chat = raise_on_chat
        self.raise_on_clear = raise_on_clear
        self.memory = self  # simple stub; clear_history defined below
        self.calls = []
        self.cleared = []

    def handle_query(self, user_id, query=None, file_content=None):
        self.calls.append((user_id, query, file_content))
        if self.raise_on_chat:
            raise RuntimeError("chat boom")
        return self.response

    def clear_history(self, user_id):
        self.cleared.append(user_id)
        if self.raise_on_clear:
            raise RuntimeError("clear boom")


class DummyReportExtractor:
    def __init__(self, result=None, raise_with=None):
        self.result = result
        self.raise_with = raise_with
        self.calls = []

    def extract(self, content: str):
        self.calls.append(content)
        if self.raise_with:
            raise self.raise_with
        return self.result


@pytest.fixture
def make_client(monkeypatch):
    """Factory to create a TestClient with a patched chat service."""

    def _make(service: DummyChatService) -> TestClient:
        monkeypatch.setattr(main, "get_chat_service", lambda: service)
        return TestClient(main.app)

    return _make


def test_root_endpoint():
    client = TestClient(main.app)
    resp = client.get("/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["version"] == "0.1.0"
    assert "Awesome Agent API" in data["message"]


def test_health_endpoint():
    client = TestClient(main.app)
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["service"] == "awesome-agent-api"
    assert data["version"] == "0.1.0"


def test_chat_endpoint_success_with_query(make_client):
    service = DummyChatService(response="handled")
    client = make_client(service)

    resp = client.post(
        "/chat",
        json={"user_id": 1, "query": "hello world"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["response"] == "handled"
    assert body["user_id"] == 1
    assert service.calls == [(1, "hello world", None)]


def test_chat_endpoint_success_with_file_only(make_client):
    service = DummyChatService(response="file received")
    client = make_client(service)

    resp = client.post(
        "/chat",
        json={"user_id": 2, "query": None, "file_content": "data from file"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["response"] == "file received"
    assert body["user_id"] == 2
    assert service.calls == [(2, None, "data from file")]


def test_chat_endpoint_failure_returns_error(make_client):
    service = DummyChatService(raise_on_chat=True)
    client = make_client(service)

    resp = client.post("/chat", json={"user_id": 3, "query": "hi"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is False
    assert "Xin lỗi" in body["response"]
    assert "chat boom" in body["error"]
    assert service.calls == [(3, "hi", None)]


def test_clear_memory_success(make_client):
    service = DummyChatService()
    client = make_client(service)

    resp = client.post("/memory/clear", params={"user_id": 42})

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert "42" in body["message"]
    assert service.cleared == [42]


def test_clear_memory_failure(make_client):
    service = DummyChatService(raise_on_clear=True)
    client = make_client(service)

    resp = client.post("/memory/clear", params={"user_id": 99})

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is False
    assert "clear boom" in body["error"]
    assert service.cleared == [99]


def test_extract_work_report_success(monkeypatch):
    extractor = DummyReportExtractor(
        result=WorkReportData(
            daily_tasks=DailyTasks(
                tasks=[
                    DailyTask(
                        id="FACE",
                        title="Test module nhận diện khuôn mặt",
                        status="in_progress",
                        progress=80,
                        time_spent="4h",
                    )
                ],
                blockers=["Thiếu bộ dataset clean"],
                achievements=[],
            ),
            notes="Ghi chú",
            created_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-01T00:00:00Z",
        )
    )
    monkeypatch.setattr(main, "get_work_report_extractor", lambda: extractor)
    client = TestClient(main.app)

    resp = client.post("/reports/extract", json={"content": "sample report"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["message"].startswith("Trích xuất báo cáo")
    assert data["data"]["daily_tasks"]["tasks"][0]["progress"] == 80
    assert data["data"]["daily_tasks"]["blockers"] == ["Thiếu bộ dataset clean"]
    assert extractor.calls == ["sample report"]


def test_extract_work_report_invalid(monkeypatch):
    extractor = DummyReportExtractor(raise_with=ValueError("Nội dung không đúng yêu cầu"))
    monkeypatch.setattr(main, "get_work_report_extractor", lambda: extractor)
    client = TestClient(main.app)

    resp = client.post("/reports/extract", json={"content": "bad report"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is False
    assert data["message"] == "Nội dung không đúng yêu cầu"
    assert "Nội dung không đúng yêu cầu" in data["error"]
    assert extractor.calls == ["bad report"]


def test_extract_work_report_inline_payload(monkeypatch):
    extractor = DummyReportExtractor(
        result=WorkReportData(
            daily_tasks=DailyTasks(
                tasks=[
                    DailyTask(
                        id="UE",
                        title="UE",
                        status="done",
                        progress=100,
                        time_spent="1h",
                    )
                ],
                blockers=[],
                achievements=[],
            ),
            notes="",
        )
    )
    monkeypatch.setattr(main, "get_work_report_extractor", lambda: extractor)
    client = TestClient(main.app)

    payload = {
        "content": "1. Today work: + Unreal Engine: abc 2. Issues: - none 3. Tomorrow plan + UE - continue"
    }
    resp = client.post("/reports/extract", json=payload)
    assert resp.status_code == 200
    assert resp.json()["success"] is True
    assert extractor.calls[-1] == payload["content"]
