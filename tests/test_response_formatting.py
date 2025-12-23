from auto_pm_agent_api.utils import markdown_to_text, format_chat_response


def test_markdown_to_text_removes_emphasis_and_keeps_content():
    md = (
        "Bạn có **3 nhiệm vụ** trong dự án **Demo**:\n\n"
        "1. **Task A**\n"
        "   - **Start**: 2025-12-15\n"
        "   - **Due**: 2025-12-25\n"
    )
    out = markdown_to_text(md)
    assert "**" not in out
    assert "3 nhiệm vụ" in out
    assert "Demo" in out
    assert "Task A" in out
    assert "- Start: 2025-12-15" in out


def test_markdown_to_text_converts_links():
    md = "Xem thêm tại [Plane](https://example.com/projects/1)."
    out = markdown_to_text(md)
    assert out == "Xem thêm tại Plane (https://example.com/projects/1)."


def test_format_chat_response_defaults_to_text(monkeypatch):
    monkeypatch.delenv("RESPONSE_FORMAT", raising=False)
    out = format_chat_response("**Hello**")
    assert out == "Hello"


def test_format_chat_response_keeps_markdown_when_configured(monkeypatch):
    monkeypatch.setenv("RESPONSE_FORMAT", "markdown")
    out = format_chat_response("**Hello**")
    assert out == "**Hello**"

