from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services import ingestion, rag, search


class FakeResponse:
    def __init__(self, status_code=200, data=None, text=""):
        self.status_code = status_code
        self._data = data or {}
        self.text = text

    def json(self):
        return self._data


class FakeHttpClient:
    def __init__(self, responses, **_kwargs):
        self.responses = iter(responses)
        self.requests = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def post(self, url, **kwargs):
        self.requests.append((url, kwargs))
        return next(self.responses)


class FakeResult:
    def __init__(self, rows):
        self.rows = rows

    def fetchall(self):
        return self.rows


class FakeSession:
    def __init__(self, rows=()):
        self.rows = rows
        self.execute_calls = []
        self.added = []
        self.committed = False
        self.begin_calls = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def execute(self, statement, params=None):
        self.execute_calls.append((str(statement), params))
        return FakeResult(self.rows)

    def add(self, instance):
        self.added.append(instance)

    async def commit(self):
        self.committed = True

    def begin(self):
        self.begin_calls += 1
        return self


async def test_embedding_client_returns_vector_and_sends_request(monkeypatch):
    client = FakeHttpClient([FakeResponse(data={"embedding": [0.1, 0.2]})])
    monkeypatch.setattr(search.httpx, "AsyncClient", lambda **kwargs: client)

    assert await search.get_embedding_from_ollama("query") == [0.1, 0.2]
    assert client.requests[0][0].endswith("/api/embeddings")
    assert client.requests[0][1]["json"]["prompt"] == "query"


@pytest.mark.parametrize("module", [search, ingestion])
async def test_embedding_client_reports_http_failure(monkeypatch, module):
    client = FakeHttpClient([FakeResponse(status_code=503, text="offline")])
    monkeypatch.setattr(module.httpx, "AsyncClient", lambda **kwargs: client)

    with pytest.raises(RuntimeError, match="offline"):
        await module.get_embedding_from_ollama("query")


async def test_search_documents_sends_vector_query(monkeypatch):
    session = FakeSession(
        [SimpleNamespace(source="guide.md", content="Relevant", distance=0.1)]
    )
    monkeypatch.setattr(search, "get_embedding_from_ollama", AsyncMock(return_value=[0.1]))
    monkeypatch.setattr(search, "SessionLocal", lambda: session)

    await search.search_documents("query", top_k=4)

    sql, params = session.execute_calls[0]
    assert "embedding <=> CAST(:query_vector AS vector)" in sql
    assert params == {"query_vector": "[0.1]", "top_k": 4}


async def test_query_rag_builds_grounded_prompt_and_returns_response(monkeypatch):
    session = FakeSession(
        [
            SimpleNamespace(source="guide.md", content="Grounded context", distance=0.1),
        ]
    )
    client = FakeHttpClient([FakeResponse(data={"response": "Grounded answer"})])
    monkeypatch.setattr(rag, "get_embedding_from_ollama", AsyncMock(return_value=[0.3]))
    monkeypatch.setattr(rag, "SessionLocal", lambda: session)
    monkeypatch.setattr(rag.httpx, "AsyncClient", lambda **kwargs: client)

    answer = await rag.query_rag("Question")

    assert answer == "Grounded answer"
    prompt = client.requests[0][1]["json"]["prompt"]
    assert "Grounded context" in prompt
    assert "Question" in prompt


async def test_query_rag_returns_generation_failure(monkeypatch):
    session = FakeSession()
    client = FakeHttpClient([FakeResponse(status_code=502, text="model unavailable")])
    monkeypatch.setattr(rag, "get_embedding_from_ollama", AsyncMock(return_value=[0.3]))
    monkeypatch.setattr(rag, "SessionLocal", lambda: session)
    monkeypatch.setattr(rag.httpx, "AsyncClient", lambda **kwargs: client)

    answer = await rag.query_rag("Question")

    assert "generation failed" in answer
    assert "model unavailable" in answer


async def test_ingest_document_file_replaces_source_chunks(tmp_path, monkeypatch):
    document = tmp_path / "guide.md"
    document.write_text("First paragraph\n\nSecond paragraph", encoding="utf-8")
    session = FakeSession()
    embed = AsyncMock(side_effect=[[0.1], [0.2]])
    monkeypatch.setattr(rag, "get_embedding_from_ollama", embed)
    monkeypatch.setattr(rag, "SessionLocal", lambda: session)

    await rag.ingest_document_file(document)

    assert embed.await_count == 2
    assert session.begin_calls == 1
    assert "DELETE FROM document_embeddings" in session.execute_calls[0][0]
    assert len(session.execute_calls) == 3
    assert session.execute_calls[1][1]["content"] == "First paragraph"
    assert session.execute_calls[2][1]["content"] == "Second paragraph"


async def test_ingest_document_file_rejects_missing_path(tmp_path):
    with pytest.raises(FileNotFoundError):
        await rag.ingest_document_file(tmp_path / "missing.md")


async def test_ingest_document_file_does_not_replace_rows_if_embedding_fails(
    tmp_path, monkeypatch
):
    document = tmp_path / "guide.md"
    document.write_text("First paragraph\n\nSecond paragraph", encoding="utf-8")
    session_factory = AsyncMock()

    async def fail_embedding(_text):
        raise RuntimeError("embedding failure")

    monkeypatch.setattr(rag, "get_embedding_from_ollama", fail_embedding)
    monkeypatch.setattr(rag, "SessionLocal", session_factory)

    with pytest.raises(RuntimeError, match="embedding failure"):
        await rag.ingest_document_file(document)

    session_factory.assert_not_called()


async def test_ingest_documents_creates_seed_documents_and_records_vectors(
    tmp_path, monkeypatch
):
    session = FakeSession()
    monkeypatch.setattr(ingestion, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(ingestion, "SessionLocal", lambda: session)
    monkeypatch.setattr(
        ingestion,
        "get_embedding_from_ollama",
        AsyncMock(return_value=[0.5] * 768),
    )

    await ingestion.ingest_documents()

    assert session.committed
    assert len(session.added) == 3
    assert {record.source for record in session.added} == {
        "docs/architecture.md",
        "docs/database.md",
        "docs/security.md",
    }
    assert all(len(record.embedding) == 768 for record in session.added)


async def test_ingest_documents_continues_when_one_embedding_fails(
    tmp_path, monkeypatch, caplog
):
    session = FakeSession()
    monkeypatch.setattr(ingestion, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(ingestion, "SessionLocal", lambda: session)
    embedding = AsyncMock(side_effect=[RuntimeError("offline"), [0.2], [0.3]])
    monkeypatch.setattr(ingestion, "get_embedding_from_ollama", embedding)

    await ingestion.ingest_documents()

    assert len(session.added) == 2
    assert session.committed
    assert "Failed to generate embedding" in caplog.text
