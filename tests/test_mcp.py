import pytest

from app.mcp import server


async def test_list_resources_returns_markdown_docs(tmp_path, monkeypatch):
    (tmp_path / "guide.md").write_text("# Guide", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("not a resource", encoding="utf-8")
    monkeypatch.setattr(server, "DOCS_DIR", tmp_path)

    resources = await server.list_resources()

    assert [resource.name for resource in resources] == ["guide.md"]
    assert resources[0].mimeType == "text/markdown"


async def test_list_resources_for_missing_directory(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "DOCS_DIR", tmp_path / "missing")
    assert await server.list_resources() == []


async def test_read_resource_reads_valid_project_resource(tmp_path, monkeypatch):
    docs = tmp_path / "docs"
    docs.mkdir()
    doc = docs / "guide.md"
    doc.write_text("# Guide", encoding="utf-8")
    monkeypatch.setattr(server, "DOCS_DIR", docs)
    uri = f"file:///{str(doc).replace(chr(92), '/')}"

    assert await server.read_resource(uri) == "# Guide"


@pytest.mark.parametrize("uri", ["file:///missing.md", "file:///outside/file.md"])
async def test_read_resource_rejects_missing_or_outside_resource(
    tmp_path, monkeypatch, uri
):
    docs = tmp_path / "docs"
    docs.mkdir()
    monkeypatch.setattr(server, "DOCS_DIR", docs)

    with pytest.raises(ValueError, match="Resource not found"):
        await server.read_resource(uri)


async def test_read_resource_rejects_other_project_files(tmp_path, monkeypatch):
    docs = tmp_path / "docs"
    docs.mkdir()
    secret_file = tmp_path / ".env"
    secret_file.write_text("PASSWORD=do-not-return", encoding="utf-8")
    monkeypatch.setattr(server, "DOCS_DIR", docs)
    uri = f"file:///{str(secret_file).replace(chr(92), '/')}"

    with pytest.raises(ValueError, match="Resource not found"):
        await server.read_resource(uri)


async def test_read_resource_rejects_non_file_and_non_file_scheme(
    tmp_path, monkeypatch
):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "folder.md").mkdir()
    monkeypatch.setattr(server, "DOCS_DIR", docs)

    with pytest.raises(ValueError, match="Resource not found"):
        await server.read_resource("https://example.com/guide.md")

    directory_uri = f"file:///{str(docs / 'folder.md').replace(chr(92), '/')}"
    with pytest.raises(ValueError, match="Resource not found"):
        await server.read_resource(directory_uri)


async def test_read_resource_rejects_symlink_escape(tmp_path, monkeypatch):
    docs = tmp_path / "docs"
    docs.mkdir()
    outside = tmp_path / "private.md"
    outside.write_text("private", encoding="utf-8")
    link = docs / "linked.md"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("Symlink creation is not permitted in this environment.")
    monkeypatch.setattr(server, "DOCS_DIR", docs)
    uri = f"file:///{str(link).replace(chr(92), '/')}"

    with pytest.raises(ValueError, match="Resource not found"):
        await server.read_resource(uri)


async def test_list_tools_exposes_search_tool():
    tools = await server.list_tools()

    assert len(tools) == 1
    assert tools[0].name == "search_devagent_docs"
    assert tools[0].inputSchema["required"] == ["question"]


async def test_call_tool_runs_rag(monkeypatch):
    async def fake_query(question):
        return f"answer: {question}"

    monkeypatch.setattr("app.services.rag.query_rag", fake_query)

    result = await server.call_tool("search_devagent_docs", {"question": "hello"})

    assert result[0].text == "answer: hello"


async def test_call_tool_surfaces_rag_failure_as_tool_content(monkeypatch):
    async def failing_query(_question):
        raise RuntimeError("backend error")

    monkeypatch.setattr("app.services.rag.query_rag", failing_query)

    result = await server.call_tool("search_devagent_docs", {"question": "hello"})

    assert "Error executing vector search: backend error" == result[0].text


async def test_call_tool_rejects_unknown_name():
    with pytest.raises(ValueError, match="Unknown tool"):
        await server.call_tool("unknown", {})
