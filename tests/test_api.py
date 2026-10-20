import pytest
from fastapi.testclient import TestClient
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.agent import executor as agent_executor
from app.main import app
from app.services import rag as rag_service


def local_client():
    return TestClient(app, client=("127.0.0.1", 12345))


class FakeQueryResult:
    def fetchall(self):
        return [SimpleNamespace(source="guide.md", content="Relevant project context")]


class FakeQuerySession:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def execute(self, *_args, **_kwargs):
        return FakeQueryResult()


class FakeGenerationClient:
    def __init__(self, response):
        self.response = response
        self.request = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def post(self, url, **kwargs):
        self.request = (url, kwargs)
        return SimpleNamespace(
            status_code=200,
            json=lambda: {"response": "Answer grounded in retrieved context"},
        )


def test_agent_endpoint_returns_agent_result(monkeypatch):
    async def fake_run_agent(goal):
        return f"Result for: {goal}"

    monkeypatch.setattr("app.main.run_react_agent", fake_run_agent)

    response = local_client().post(
        "/api/agent/run",
        json={"goal": "Check git status"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "success",
        "result": "Result for: Check git status",
    }


def test_agent_endpoint_reports_agent_failure(monkeypatch):
    async def failing_agent(_goal):
        raise RuntimeError("agent unavailable")

    monkeypatch.setattr("app.main.run_react_agent", failing_agent)

    response = local_client().post("/api/agent/run", json={"goal": "Check status"})

    assert response.status_code == 500
    assert response.json()["detail"] == "Agent execution failed."


def test_agent_endpoint_rejects_non_loopback_client(monkeypatch):
    async def should_not_run(_goal):
        raise AssertionError("agent must not run for remote clients")

    monkeypatch.setattr("app.main.run_react_agent", should_not_run)
    response = TestClient(app, client=("203.0.113.10", 12345)).post(
        "/api/agent/run", json={"goal": "Run a task"}
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Agent execution is only available from this computer."


def test_agent_endpoint_rejects_blank_goal(monkeypatch):
    response = local_client().post("/api/agent/run", json={"goal": "  "})

    assert response.status_code == 422


def test_agent_endpoint_rejects_non_string_goal():
    response = local_client().post(
        "/api/agent/run",
        json={"goal": ["not", "a", "string"]},
    )

    assert response.status_code == 422


def test_agent_endpoint_rejects_goal_over_limit():
    response = local_client().post("/api/agent/run", json={"goal": "x" * 4001})

    assert response.status_code == 422


def test_rag_endpoint_returns_answer(monkeypatch):
    async def fake_query_rag(question):
        return f"Answer for: {question}"

    monkeypatch.setattr("app.main.query_rag", fake_query_rag)

    response = local_client().post(
        "/api/rag/query",
        json={"question": "How are tools validated?"},
    )

    assert response.status_code == 200
    assert response.json() == {"status": "success", "answer": "Answer for: How are tools validated?"}


def test_rag_endpoint_runs_pipeline_with_mocked_database_and_model(monkeypatch):
    client = FakeGenerationClient(response=None)
    monkeypatch.setattr(
        rag_service, "get_embedding_from_ollama", AsyncMock(return_value=[0.1, 0.2])
    )
    monkeypatch.setattr(rag_service, "SessionLocal", lambda: FakeQuerySession())
    monkeypatch.setattr(rag_service.httpx, "AsyncClient", lambda **_kwargs: client)

    response = local_client().post(
        "/api/rag/query",
        json={"question": "Where does the documentation come from?"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "success",
        "answer": "Answer grounded in retrieved context",
    }
    assert client.request[0].endswith("/api/generate")
    prompt = client.request[1]["json"]["prompt"]
    assert "Relevant project context" in prompt
    assert "Where does the documentation come from?" in prompt


def test_rag_endpoint_reports_failure(monkeypatch):
    async def failing_query(_question):
        raise RuntimeError("backend unavailable")

    monkeypatch.setattr("app.main.query_rag", failing_query)

    response = local_client().post(
        "/api/rag/query",
        json={"question": "How are tools validated?"},
    )

    assert response.status_code == 500
    assert response.json()["detail"] == "RAG query failed."


def test_agent_endpoint_requires_goal():
    response = local_client().post("/api/agent/run", json={})

    assert response.status_code == 422


def test_rag_endpoint_requires_question():
    response = local_client().post("/api/rag/query", json={})

    assert response.status_code == 422


@pytest.mark.parametrize("question", ["", " ", "\t\n"])
def test_rag_endpoint_rejects_empty_or_whitespace_question(question, monkeypatch):
    async def should_not_run(_question):
        raise AssertionError("RAG should not run for a blank question")

    monkeypatch.setattr("app.main.query_rag", should_not_run)
    response = local_client().post("/api/rag/query", json={"question": question})

    assert response.status_code == 422


def test_rag_endpoint_rejects_question_over_limit():
    response = local_client().post(
        "/api/rag/query",
        json={"question": "x" * 4001},
    )

    assert response.status_code == 422


def test_rag_endpoint_rejects_non_string_question():
    response = local_client().post("/api/rag/query", json={"question": ["question"]})

    assert response.status_code == 422


def test_rag_endpoint_does_not_leak_upstream_exception(monkeypatch, caplog):
    async def failing_query(_question):
        raise RuntimeError("private database connection details")

    monkeypatch.setattr("app.main.query_rag", failing_query)
    response = local_client().post(
        "/api/rag/query",
        json={"question": "What is in the docs?"},
    )

    assert response.status_code == 500
    assert response.json()["detail"] == "RAG query failed."
    assert "private database connection details" not in response.text
    assert "RAG query failed" in caplog.text


def test_agent_endpoint_does_not_leak_upstream_exception(monkeypatch, caplog):
    async def failing_agent(_goal):
        raise RuntimeError("private Ollama URL and credentials")

    monkeypatch.setattr("app.main.run_react_agent", failing_agent)
    response = local_client().post("/api/agent/run", json={"goal": "Read the documentation"})

    assert response.status_code == 500
    assert response.json()["detail"] == "Agent execution failed."
    assert "private Ollama URL and credentials" not in response.text
    assert "Agent execution failed" in caplog.text


def test_agent_endpoint_handles_ollama_connection_failure_without_leaking(
    monkeypatch,
):
    class FailingClient:
        def __init__(self, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, *_args, **_kwargs):
            raise agent_executor.httpx.ConnectError("private endpoint details")

    monkeypatch.setattr(agent_executor.httpx, "AsyncClient", FailingClient)

    response = local_client().post("/api/agent/run", json={"goal": "Check service health"})

    assert response.status_code == 500
    assert response.json()["detail"] == "Agent execution failed."
    assert "private endpoint details" not in response.text
