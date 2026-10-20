import httpx
import pytest

from app.agent import executor


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ('file_path="app/main.py"', {"file_path": "app/main.py"}),
        ("query='two words', top_k=3", {"query": "two words", "top_k": "3"}),
        ("enabled=true, count=0", {"enabled": "true", "count": "0"}),
        ("", {}),
    ],
)
def test_parse_tool_args(source, expected):
    assert executor.parse_tool_args(source) == expected


class FakeResponse:
    def __init__(self, content, status_code=200, text=""):
        self.status_code = status_code
        self.text = text
        self._content = content

    def json(self):
        return {"message": {"content": self._content}}


class FakeAsyncClient:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.requests = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def post(self, url, **kwargs):
        self.requests.append((url, kwargs))
        return next(self.responses)


def install_client(monkeypatch, responses):
    client = FakeAsyncClient(responses)
    monkeypatch.setattr(executor.httpx, "AsyncClient", lambda **_kwargs: client)
    return client


async def test_agent_returns_final_answer(monkeypatch):
    client = install_client(
        monkeypatch,
        [FakeResponse("THOUGHT: done\nFINAL_ANSWER: Everything is ready.")],
    )

    result = await executor.run_react_agent("Check readiness")

    assert result == "Everything is ready."
    assert len(client.requests) == 1
    assert client.requests[0][0].endswith("/api/chat")


async def test_agent_executes_known_tool_and_returns_followup(monkeypatch):
    observations = []

    def fake_tool(**kwargs):
        observations.append(kwargs)
        return "file contents"

    monkeypatch.setitem(
        executor.AVAILABLE_TOOLS,
        "test_tool",
        {"function": fake_tool},
    )
    client = install_client(
        monkeypatch,
        [
            FakeResponse('THOUGHT: inspect\nTOOL: test_tool(path="app/main.py")'),
            FakeResponse("FINAL_ANSWER: Inspection complete."),
        ],
    )

    result = await executor.run_react_agent("Inspect", max_turns=2)

    assert result == "Inspection complete."
    assert observations == [{"path": "app/main.py"}]
    history = client.requests[1][1]["json"]["messages"]
    assert any("OBSERVATION: file contents" in item["content"] for item in history)


async def test_agent_reports_unknown_tool_to_model(monkeypatch):
    client = install_client(
        monkeypatch,
        [
            FakeResponse("TOOL: missing_tool()"),
            FakeResponse("FINAL_ANSWER: The tool was unavailable."),
        ],
    )

    result = await executor.run_react_agent("Try unavailable tool", max_turns=2)

    assert result == "The tool was unavailable."
    history = client.requests[1][1]["json"]["messages"]
    assert any("does not exist" in item["content"] for item in history)


async def test_agent_returns_ollama_http_error(monkeypatch):
    install_client(monkeypatch, [FakeResponse("", status_code=503, text="offline")])

    result = await executor.run_react_agent("Check service")

    assert result == "Agent failed to communicate with Ollama: offline"


async def test_agent_propagates_ollama_connection_failure(monkeypatch):
    class FailingClient(FakeAsyncClient):
        async def post(self, _url, **_kwargs):
            raise httpx.ConnectError("Ollama unavailable")

    client = FailingClient([])
    monkeypatch.setattr(executor.httpx, "AsyncClient", lambda **_kwargs: client)

    with pytest.raises(httpx.ConnectError, match="Ollama unavailable"):
        await executor.run_react_agent("Check service")


async def test_agent_propagates_malformed_ollama_response(monkeypatch):
    class InvalidJsonResponse:
        status_code = 200
        text = "not-json"

        def json(self):
            raise ValueError("invalid JSON")

    install_client(monkeypatch, [InvalidJsonResponse()])

    with pytest.raises(ValueError, match="invalid JSON"):
        await executor.run_react_agent("Check service")


async def test_agent_stops_at_max_turns(monkeypatch):
    install_client(monkeypatch, [FakeResponse("I need to think more")])

    result = await executor.run_react_agent("Unfinished", max_turns=1)

    assert result == "Agent reached maximum execution turns without completing the task."


async def test_agent_accepts_final_answer_on_last_allowed_turn(monkeypatch):
    install_client(
        monkeypatch,
        [FakeResponse("FINAL_ANSWER: Finished on the final turn.")],
    )

    assert await executor.run_react_agent("Finish", max_turns=1) == (
        "Finished on the final turn."
    )


async def test_agent_handles_tool_exception(monkeypatch):
    def broken_tool():
        raise RuntimeError("tool failure")

    monkeypatch.setitem(
        executor.AVAILABLE_TOOLS,
        "broken_tool",
        {"function": broken_tool},
    )
    client = install_client(
        monkeypatch,
        [
            FakeResponse("TOOL: broken_tool()"),
            FakeResponse("FINAL_ANSWER: Recovered."),
        ],
    )

    assert await executor.run_react_agent("Run tool", max_turns=2) == "Recovered."
    history = client.requests[1][1]["json"]["messages"]
    assert any("Error executing tool: tool failure" in item["content"] for item in history)


async def test_agent_retries_with_reminder_when_response_has_no_action(monkeypatch):
    client = install_client(
        monkeypatch,
        [
            FakeResponse("Unstructured response"),
            FakeResponse("FINAL_ANSWER: Completed."),
        ],
    )

    assert await executor.run_react_agent("Try again", max_turns=2) == "Completed."
    history = client.requests[1][1]["json"]["messages"]
    assert any("REMINDER:" in item["content"] for item in history)
