# Security notes

DevAgent Core is intended for trusted, local development. It is not designed
as a production multi-user service.

## Current safeguards

- The ReAct API route rejects requests whose client address is not loopback.
- The agent file tools resolve paths and restrict reads/writes to the project
  root; writes can still replace any file within that root.
- The agent command tool allows only `git status` and `git status --short`,
  executed without a shell.
- MCP resource reads are restricted to Markdown files inside the resolved
  `docs/` directory.
- `.env` and common local environment/test artifacts are excluded by
  `.gitignore`. This does not replace reviewing the exact files before
  publishing.

## Deployment boundaries

- Keep Uvicorn bound to `127.0.0.1`. Do not expose the dashboard/API through a
  public interface, reverse proxy, or shared network without adding suitable
  authentication, authorization, and request protections.
- The agent can read and modify project files. Run it only against a workspace
  where those actions are acceptable.
- The RAG API route does not provide user authentication. Keep the whole
  application local, not just the agent route.
- Compose publishes PostgreSQL on the host for local development. Do not reuse
  the example password or expose the database port to untrusted networks.
- Ollama is also a local dependency; do not expose its service to untrusted
  clients.
- Review `.env`, generated data, logs, and all staged files before any public
  repository upload. Never commit credentials, private documents, or local
  database contents.

These protections are not a substitute for a security assessment before any
deployment beyond a single trusted developer machine.
