# DevAgent Core

DevAgent Core is a local-first developer assistant that combines a FastAPI
dashboard, an Ollama-backed ReAct agent, PostgreSQL/pgvector document search,
and an MCP stdio server.

## What it does

- Runs a bounded ReAct loop with project-file read/write tools and a
  read-only Git status command.
- Answers documentation questions using Ollama embeddings, PostgreSQL with
  pgvector, and local Ollama generation.
- Exposes Markdown resources and a RAG search tool over MCP.
- Includes a Markdown file watcher and Selenium browser tests.

This is a development project, not a hardened multi-user service. The agent API
is restricted to loopback clients and can write files under the project root.
Do not expose it directly to the internet or run it against a project containing
files you are not willing to let the agent read or modify.

## Get started

See [GUIDEME.md](./GUIDEME.md) for Windows PowerShell setup, Docker/PostgreSQL
configuration, Ollama model installation, database initialization, tests, and
troubleshooting.

## Architecture

See [ARCHITECTURE.md](./ARCHITECTURE.md) for the current application flow.

## License

This project is licensed under the [MIT License](./LICENSE).
