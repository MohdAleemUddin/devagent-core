import subprocess

import pytest
from pydantic import BaseModel

from app.agent import tools as agent_tools
from app.tools import executor as tools_executor
from app.tools import implementations
from app.tools.registry import ToolRegistry


def test_registry_registers_and_exports_schema():
    registry = ToolRegistry()

    class Args(BaseModel):
        value: str

    @registry.register("example", "Example tool", Args)
    async def example(value: str):
        return value

    tool = registry.get_tool("example")
    schema = registry.get_all_schemas()[0]

    assert tool.func is example
    assert schema["function"]["name"] == "example"
    assert schema["function"]["parameters"]["required"] == ["value"]


def test_registry_rejects_unknown_tool():
    with pytest.raises(ValueError, match="not registered"):
        ToolRegistry().get_tool("missing")


async def test_tool_registry_executes_async_and_sync_functions():
    registry = ToolRegistry()

    class Args(BaseModel):
        value: int

    @registry.register("sync", "Sync function", Args)
    def sync_tool(value: int):
        return value + 1

    @registry.register("async", "Async function", Args)
    async def async_tool(value: int):
        return value + 2

    assert await registry.get_tool("sync").execute(value=2) == 3
    assert await registry.get_tool("async").execute(value=2) == 4


async def test_execute_tool_call_validates_and_executes():
    import app.tools.implementations  # Register built-in tools.

    result = await tools_executor.execute_tool_call(
        "query_logs",
        {"severity": "error", "limit": 1},
    )

    assert "Found 1 log(s) for severity ERROR" in result
    assert "Failed to connect" in result


async def test_execute_tool_call_handles_unknown_tool():
    result = await tools_executor.execute_tool_call("not_registered", {})
    assert "does not exist" in result


async def test_execute_tool_call_handles_invalid_arguments():
    result = await tools_executor.execute_tool_call("query_logs", {"limit": 0})
    assert "Invalid arguments" in result


async def test_execute_tool_call_converts_tool_exception_to_error(monkeypatch):
    class FailingTool:
        args_schema = type("Args", (BaseModel,), {})

        async def execute(self, **_kwargs):
            raise RuntimeError("execution failed")

    monkeypatch.setattr(tools_executor.tool_registry, "get_tool", lambda _name: FailingTool())

    result = await tools_executor.execute_tool_call("failing", {})

    assert result == "Error executing tool 'failing': execution failed"


async def test_read_file_returns_contents_and_handles_missing_path(tmp_path, monkeypatch):
    monkeypatch.setattr(implementations, "PROJECT_ROOT", tmp_path)
    source = tmp_path / "sample.txt"
    source.write_text("hello", encoding="utf-8")

    assert await implementations.read_file_tool("sample.txt") == "hello"
    assert "does not exist" in await implementations.read_file_tool("missing.txt")


async def test_read_file_rejects_directories(tmp_path, monkeypatch):
    monkeypatch.setattr(implementations, "PROJECT_ROOT", tmp_path)
    (tmp_path / "folder").mkdir()

    assert "is a directory" in await implementations.read_file_tool("folder")


async def test_read_file_rejects_path_outside_root(tmp_path, monkeypatch):
    root = tmp_path / "project"
    sibling = tmp_path / "project-secrets"
    root.mkdir()
    sibling.mkdir()
    (sibling / "secret.txt").write_text("secret", encoding="utf-8")
    monkeypatch.setattr(implementations, "PROJECT_ROOT", root)

    result = await implementations.read_file_tool("../project-secrets/secret.txt")

    assert "Access denied" in result


async def test_query_logs_normalizes_severity_limits_and_empty_results():
    assert "Found 1 log(s) for severity ERROR" in await implementations.query_logs_tool(
        "error", limit=1
    )
    assert "Invalid severity 'DEBUG'" in await implementations.query_logs_tool("DEBUG")


def test_agent_file_tool_blocks_path_escape(tmp_path, monkeypatch):
    root = tmp_path / "project"
    sibling = tmp_path / "project-secrets"
    root.mkdir()
    sibling.mkdir()
    (sibling / "secret.txt").write_text("secret", encoding="utf-8")
    monkeypatch.setattr(agent_tools, "PROJECT_ROOT", root)

    result = agent_tools.tool_read_file("../project-secrets/secret.txt")

    assert "Access denied" in result


def test_agent_file_tools_read_and_write_under_root(tmp_path, monkeypatch):
    monkeypatch.setattr(agent_tools, "PROJECT_ROOT", tmp_path)

    assert agent_tools.tool_write_file("nested/file.txt", "data") == (
        "Successfully wrote to nested/file.txt"
    )
    assert agent_tools.tool_read_file("nested/file.txt") == "data"


def test_agent_command_blocks_known_dangerous_commands(monkeypatch):
    def should_not_run(*_args, **_kwargs):
        raise AssertionError("unsupported command must not execute")

    monkeypatch.setattr(agent_tools.subprocess, "run", should_not_run)

    assert "not allowed" in agent_tools.tool_run_command("rm -rf /")


@pytest.mark.parametrize(
    "command",
    [
        "git status && whoami",
        "git status; whoami",
        "git status --short && del secrets.txt",
        "python -c \"print('bad')\"",
        "",
    ],
)
def test_agent_command_rejects_unlisted_commands_and_injection(monkeypatch, command):
    def should_not_run(*_args, **_kwargs):
        raise AssertionError("unlisted command must not execute")

    monkeypatch.setattr(agent_tools.subprocess, "run", should_not_run)

    assert "not allowed" in agent_tools.tool_run_command(command)


def test_agent_command_runs_only_literal_git_status_without_shell(monkeypatch):
    calls = []

    def fake_run(args, **kwargs):
        calls.append((args, kwargs))
        return subprocess.CompletedProcess(
            args=args, returncode=0, stdout=" M file.txt\n", stderr=""
        )

    monkeypatch.setattr(agent_tools.subprocess, "run", fake_run)

    assert agent_tools.tool_run_command("git status --short") == "M file.txt"
    assert calls[0][0] == ["git", "status", "--short"]
    assert calls[0][1]["shell"] is False


def test_agent_command_reports_output_and_timeout(monkeypatch):
    monkeypatch.setattr(
        agent_tools.subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            args=["git", "status"], returncode=0, stdout="ok\n", stderr=""
        ),
    )
    assert agent_tools.tool_run_command("git status") == "ok"

    def timeout(*_args, **_kwargs):
        raise subprocess.TimeoutExpired("sleep", 30)

    monkeypatch.setattr(agent_tools.subprocess, "run", timeout)
    assert agent_tools.tool_run_command("git status") == (
        "Error: Command timed out after 10 seconds."
    )
