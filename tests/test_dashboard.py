from html.parser import HTMLParser

from fastapi.testclient import TestClient

from app.main import app


class AgentGoalButtonParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.goals = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "button" and "data-agent-goal" in attributes:
            self.goals.append(attributes["data-agent-goal"])


def test_write_file_example_button_has_clickable_goal():
    response = TestClient(app).get("/")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    parser = AgentGoalButtonParser()
    parser.feed(response.text)

    assert parser.goals == [
        'Use write_file to create a file at docs/about_project.md with content '
        '"This RAG agent project is built using Ollama, MCP, and pgvector."',
        "Use run_command to check git status in the project root.",
    ]
    assert "button.addEventListener('click'" in response.text
    assert 'id="agentToken"' not in response.text
    assert "window.prompt" not in response.text
    assert "'Authorization'" not in response.text
    assert "response.ok && data.status === 'success'" in response.text
    assert "data.detail || JSON.stringify(data)" in response.text


def test_rag_dashboard_handles_http_failures():
    response = TestClient(app).get("/")

    assert response.status_code == 200
    assert "response.ok && data.status === 'success'" in response.text
    assert "data.detail || JSON.stringify(data)" in response.text
