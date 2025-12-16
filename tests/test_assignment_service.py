import os
import pytest

from auto_pm_agent_api.application.assignment_service.assignment_service import (
    AssignmentService,
)


class DummyLLM:
    def generate_response(self, *args, **kwargs):
        return None


class DummyPlaneFactory:
    def get_api(self, user_id=None):
        return None


class PlaneMemberStub:
    def __init__(self, mid="m1", email="m1@example.com", name="Member One", role="dev"):
        self.id = mid
        self.email = email
        self.display_name = name
        self.role = role


class FakeResponse:
    def __init__(self, status_code=200, data=None):
        self.status_code = status_code
        self._data = data or {}

    def json(self):
        return self._data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


@pytest.fixture(autouse=True)
def set_user_service_env(monkeypatch):
    monkeypatch.setenv("USER_SERVICE_BASE_URL", "http://localhost:8000")
    yield
    monkeypatch.delenv("USER_SERVICE_BASE_URL", raising=False)


def test_fetch_member_profile_by_id(monkeypatch):
    called = {}

    def fake_get(url, timeout=10):
        called["url"] = url
        return FakeResponse(
            200,
            {
                "id": "u123",
                "email": "u@example.com",
                "zalo_metadata": {"skills": ["python"], "experience_years": 2},
            },
        )

    monkeypatch.setattr(
        "auto_pm_agent_api.application.assignment_service.assignment_service.requests.get",
        fake_get,
    )
    svc = AssignmentService(DummyLLM(), DummyPlaneFactory())

    profile = svc._fetch_member_profile(member_id="u123", email="u@example.com")

    assert profile["id"] == "u123"
    assert "python" in profile["zalo_metadata"]["skills"]
    assert called["url"].endswith("/api/users/u123/with-zalo/")


def test_enrich_members_uses_profile_and_workload(monkeypatch):
    def fake_get(url, timeout=10):
        return FakeResponse(
            200,
            {
                "display_name": "Profile Name",
                "zalo_metadata": {
                    "skills": ["go", "python"],
                    "experience_years": 5,
                    "experience_level": "senior",
                },
            },
        )

    monkeypatch.setattr(
        "auto_pm_agent_api.application.assignment_service.assignment_service.requests.get",
        fake_get,
    )
    svc = AssignmentService(DummyLLM(), DummyPlaneFactory())
    members = [PlaneMemberStub(mid="m42", name="Fallback Name")]
    workload = {"m42": 3}

    enriched = svc._enrich_members(members, workload)

    assert enriched[0]["id"] == "m42"
    assert enriched[0]["name"] == "Profile Name"
    assert enriched[0]["workload"] == 3
    assert enriched[0]["skills"] == ["go", "python"]
    assert enriched[0]["experience_years"] == 5
