# DevAgent Core architecture

DevAgent Core is a local development application composed of a FastAPI
dashboard, an Ollama-backed ReAct agent, a PostgreSQL/pgvector RAG pipeline,
an optional Markdown watcher, and an MCP stdio server.

## Components and data flow

```text
Browser
  └── FastAPI dashboard
       ├── ReAct executor ──► project file tools / read-only Git status
       └── RAG query ───────► PostgreSQL + pgvector ──► Ollama

Markdown files in docs/
  ├── explicit seed ingestion
  └── optional watcher ────► Ollama embeddings ──────► PostgreSQL + pgvector

MCP client (stdio)
  ├── Markdown resources from docs/
  └── RAG search tool ─────► PostgreSQL + pgvector / Ollama
```

## ReAct agent

`app/agent/executor.py` runs the model/tool interaction loop. Its tools are
registered in `app/agent/tools.py`:

- `read_file` reads files under the resolved project root.
- `write_file` creates or overwrites files under the resolved project root.
- `run_command` supports only the literal `git status` and
  `git status --short` commands, invoked without a shell.

The agent API route checks that the connecting client address is loopback.
The UI and API are intended for local use. Bind Uvicorn to `127.0.0.1`; do not
expose the app or its project-write capability to an untrusted network.

## Retrieval-augmented generation

`app/services/rag.py` splits Markdown on blank lines, requests embeddings from
Ollama using `nomic-embed-text`, stores chunks and vectors in PostgreSQL with
pgvector, and retrieves similar chunks for RAG answers. Generation and
embeddings are currently invoked with hardcoded Ollama model names; the
`MODEL_NAME` and `LLM_PROVIDER` settings do not currently configure those
calls.

`python -m app.core.init_db` enables the vector extension and initializes the
embedding table. `python -m app.services.run_ingestion` ingests the three
sample documents selected by that command; it is not a general recursive
indexer for every file in `docs/`.

## Document watcher

The watcher is a separate process launched with
`python -m app.services.watcher`; the web server does not start it. It observes
Markdown files directly inside `docs/` (not recursively), debounces changes,
uses SHA-256 to skip unchanged content, and submits ingestion work to a
persistent asyncio loop.

## MCP server

`python -m app.mcp.server` starts the MCP stdio server. Its resource listing
contains Markdown files directly under `docs/`; resource reads resolve paths
and reject files outside that directory, non-Markdown files, and missing
files. Its `search_devagent_docs` tool calls the same RAG query function and
therefore requires the database and Ollama to be available.

## Runtime stack

| Layer | Technology | Role |
| --- | --- | --- |
| Web/API | FastAPI, Uvicorn | Dashboard and HTTP endpoints |
| Agent | Ollama, Python | ReAct reasoning and tool execution |
| Retrieval | PostgreSQL, pgvector, Ollama | Chunk storage, vector search, and answer generation |
| Watcher | watchdog, asyncio | Optional Markdown change detection and ingestion |
| Tool protocol | MCP Python SDK | Stdio resources and RAG search |
