import pytest
from pydantic import ValidationError

from app.schemas.agent_schemas import AgentRunRequest, AgentRunResponse
from app.schemas.tool_schemas import (
    QueryLogsToolSchema,
    ReadFileToolSchema,
    VectorSearchToolSchema,
)


def test_agent_request_defaults_and_bounds():
    request = AgentRunRequest(prompt="Inspect this project")
    assert request.max_steps == 5
    assert request.session_id is None

    assert AgentRunRequest(prompt="Inspect", max_steps=1).max_steps == 1
    assert AgentRunRequest(prompt="Inspect", max_steps=15).max_steps == 15

    for value in (0, 16):
        with pytest.raises(ValidationError):
            AgentRunRequest(prompt="Inspect", max_steps=value)


@pytest.mark.parametrize("prompt", ["", None])
def test_agent_request_requires_nonempty_prompt(prompt):
    with pytest.raises(ValidationError):
        AgentRunRequest(prompt=prompt)


def test_agent_response_accepts_steps_and_uuid():
    response = AgentRunResponse(
        session_id="3d0f6b18-e33a-4c59-8c56-841bcf704195",
        status="completed",
        final_response="Done",
        steps_taken=[{"step": 1, "action": "read_file"}],
    )

    assert response.steps_taken[0].action == "read_file"
    assert response.final_response == "Done"


def test_log_tool_schema_enforces_limit():
    assert QueryLogsToolSchema(severity="ERROR").limit == 5
    assert QueryLogsToolSchema(severity="INFO", limit=20).limit == 20

    for limit in (0, 21):
        with pytest.raises(ValidationError):
            QueryLogsToolSchema(severity="INFO", limit=limit)


def test_vector_search_schema_enforces_top_k():
    assert VectorSearchToolSchema(query="search").top_k == 3
    assert VectorSearchToolSchema(query="search", top_k=10).top_k == 10

    for top_k in (0, 11):
        with pytest.raises(ValidationError):
            VectorSearchToolSchema(query="search", top_k=top_k)


def test_read_file_schema_requires_path():
    assert ReadFileToolSchema(file_path="README.md").file_path == "README.md"
    with pytest.raises(ValidationError):
        ReadFileToolSchema()

