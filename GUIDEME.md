# DevAgent Core: setup and run guide

This guide starts the project locally on Windows with PowerShell. It also
includes the equivalent commands for other shells where they differ.

## Prerequisites

- Python 3.11
- Git
- Docker Desktop with Docker Compose
- Ollama installed and running
- Chrome or Edge for the Selenium browser test

The app runs on `http://127.0.0.1:8000`. PostgreSQL uses the pgvector image and
is exposed to the host on port `5433`. Ollama uses its default local URL,
`http://localhost:11434`.

## 1. Create the environment

From the project root:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

The example `.env` values match the local Docker Compose configuration. The
default PostgreSQL password is only for machine-local development; change it
before using this configuration in any shared environment. Never commit `.env`.

## 2. Start PostgreSQL with pgvector

```powershell
docker compose up -d postgres
docker compose ps
docker compose exec postgres pg_isready -U postgres -d devagent_db
```

The Compose service binds PostgreSQL to host port `5433`, which matches
`POSTGRES_PORT` in `.env`. Do not expose this development database port to an
untrusted network.

## 3. Start Ollama and download models

Make sure Ollama is running, then download both models used by the code:

```powershell
ollama pull llama3.2:3b
ollama pull nomic-embed-text
```

The ReAct agent and RAG answer generation currently use `llama3.2:3b`.
Embedding calls use `nomic-embed-text:latest`. `MODEL_NAME` and
`LLM_PROVIDER` are present in settings, but the current calls use these model
names directly.

## 4. Initialize and seed the database

Run once after PostgreSQL is ready:

```powershell
python -m app.core.init_db
python -m app.services.run_ingestion
```

The initialization step enables the PostgreSQL `vector` extension and creates
the embedding table. The seed ingestion command indexes the sample architecture,
database, and security documents. Re-running it currently inserts those seed
records again.

## 5. Run the dashboard/API

From the project root, with the virtual environment active:

```powershell
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Open <http://127.0.0.1:8000/>. The **Execute Agent Goal** button runs the
agent without an API token prompt. The agent endpoint only accepts loopback
requests; keep the server bound to `127.0.0.1`. The agent can read and write
project files and inspect Git status, so do not expose it to other machines.

The dashboard loads Tailwind CSS from its CDN, so styling requires internet
access unless the frontend is changed to bundle Tailwind locally.

## Optional: keep Markdown embeddings synchronized

The watcher is a separate process. In another terminal with the environment
active:

```powershell
.\.venv\Scripts\Activate.ps1
python -m app.services.watcher
```

It watches Markdown files directly inside `docs/` and indexes a changed file
after its debounce interval. It requires the database and Ollama to be running.
Stop it with `Ctrl+C`.

## Optional: run the MCP server

```powershell
python -m app.mcp.server
```

This is an MCP stdio server intended to be launched by an MCP-compatible client.
It exposes Markdown documents in `docs/` and the RAG search tool. The database
and Ollama must be available before calling the search tool.

## Tests

Run the complete suite:

```powershell
$env:NO_PROXY = "localhost,127.0.0.1"
python -m pytest -v
```

The Selenium test opens Chrome or Edge visibly by default. It starts a local
test server, stubs Ollama/database responses, exercises the dashboard and ReAct
tool loop, and creates its test file only in a temporary directory.

To slow the browser walkthrough and keep the window open longer:

```powershell
$env:E2E_STEP_DELAY = "2"
$env:E2E_HOLD_SECONDS = "15"
python -m pytest tests/e2e/test_dashboard_selenium.py -v -s
```

For headless browser execution:

```powershell
$env:E2E_HEADLESS = "1"
python -m pytest tests/e2e/test_dashboard_selenium.py -v
```

Selenium Manager may need network access on first run to obtain a compatible
browser driver. The default suite includes the browser test; if you only want
the non-browser tests, run:

```powershell
python -m pytest tests --ignore=tests/e2e -v
```

## Troubleshooting

- **Settings validation fails:** Confirm `.env` exists at the project root and
  contains valid PostgreSQL host, user, password, database, and port values.
- **Database connection refused:** Check `docker compose ps` and confirm
  `.env` uses `POSTGRES_SERVER=localhost` and `POSTGRES_PORT=5433`.
- **Missing vector extension/table:** Run `python -m app.core.init_db` after
  the database is healthy.
- **Ollama connection/model errors:** Confirm Ollama is running at
  `OLLAMA_BASE_URL` and both model pulls completed.
- **Browser test cannot start:** Install Chrome or Edge and allow Selenium
  Manager to download a compatible driver. Headless mode is available through
  `E2E_HEADLESS=1`.
- **Port conflict:** Change `POSTGRES_PORT` in `.env`; Docker Compose reads the
  same value for the host-side database port. Keep the application's database
  port setting in sync.
