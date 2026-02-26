# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

WorkIQ backend — a FastAPI service that proxies Microsoft 365 Copilot and Graph API calls using the OAuth 2.0 authorization code flow (confidential client). No tokens ever reach the browser.

## Python Environment
Always use `.venv/bin/python` instead of `python3` when running scripts.
Or activate the venv first: `source .venv/bin/activate`

## Commands

All commands use `uv` as the package manager.

```bash
# Install dependencies
uv sync

# Run dev server (hot-reload)
uv run python main.py
# or
uv run uvicorn app.main:app --reload

# Run tests
uv run pytest

# Run a single test file
uv run pytest tests/test_graph_endpoint.py -v

# Build Docker image
docker build -t workiq-backend .

# Run Docker container
docker run -p 8000:8000 --env-file .env workiq-backend
```

## Required Environment Variables

Create a `.env` file in the project root:

```
TENANT_ID=<Azure Entra ID tenant GUID>
CLIENT_ID=<App registration client ID>
CLIENT_SECRET=<App registration client secret>
SECRET_KEY=<random 32-byte hex — python -c "import secrets; print(secrets.token_hex(32))">
REDIRECT_URI=http://localhost:8000/auth/callback   # must match Entra ID registration
FRONTEND_URL=http://localhost:5173
ALLOWED_ORIGINS=http://localhost:5173,http://localhost:3000
```

## Architecture

### Request Flow

```
Browser → Frontend → Backend (session cookie) → Microsoft Graph API
```

Auth is a confidential-client auth-code flow: the browser is redirected to Microsoft login, the backend exchanges the code for tokens, and all tokens are stored **server-side** (`app.state.token_cache_store`, keyed by UUID). Only the UUID key is written into the signed session cookie. This means Graph tokens never touch the browser.

### Service Lifecycle

Services are instantiated once at startup in `app/main.py`'s `lifespan` context manager and stored on `app.state`:

- `app.state.auth_service` — `AuthService`: wraps MSAL for the auth-code flow
- `app.state.copilot_service` — `CopilotService`: calls the Graph beta Copilot Chat API
- `app.state.graph_service` — `GraphService`: calls Graph v1.0 endpoints in parallel (mail, calendar, Teams, files, people, search)
- `app.state.retrieval_service` — `RetrievalService`: calls the Graph beta Copilot Retrieval API
- `app.state.token_cache_store` — `dict[str, str]`: server-side MSAL token cache (not persistent; dev only)

### Key Files

| Path | Purpose |
|------|---------|
| `app/main.py` | App factory, middleware (CORS, SessionMiddleware), router registration |
| `app/config.py` | `Settings` via pydantic-settings; loaded once and cached with `@lru_cache` |
| `app/dependencies.py` | `get_current_user` and `get_graph_token` FastAPI dependencies — used on every protected route |
| `app/routes/auth.py` | `/auth/login`, `/auth/callback`, `/auth/logout`, `/auth/me` |
| `app/routes/copilot.py` | `/api/v1/copilot_chat`, `/api/v1/graph_api`, `/api/v1/retrieval_api` |
| `app/services/auth.py` | MSAL `ConfidentialClientApplication` wrapper; per-request cache deserialise→use→reserialise pattern |
| `app/services/copilot.py` | Multi-turn Copilot Chat API calls (creates conversation if no `conversation_id`) |
| `app/services/graph.py` | Parallel `asyncio.gather` across 6 Graph endpoints; formats results as Markdown |
| `app/services/retrieval.py` | Parallel retrieval from SharePoint, OneDrive, and Connectors; merges and sorts by relevance score |
| `app/models/copilot.py` | `CopilotChatRequest` / `CopilotChatResponse` / `Attribution` — shared by all three API routes |

### API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /auth/login` | Initiates OAuth flow → redirect to Microsoft |
| `GET /auth/callback` | Microsoft redirects here with `?code=...`; exchanges for tokens |
| `GET /auth/logout` | Clears session, redirects to Microsoft logout |
| `GET /auth/me` | Returns `{name, email}` if signed in (frontend uses this to check auth state) |
| `POST /api/v1/copilot_chat` | Asks M365 Copilot Chat (Microsoft LLM answers grounded in user's M365 data) |
| `POST /api/v1/graph_api` | Fetches raw M365 data from Graph (no LLM) |
| `POST /api/v1/retrieval_api` | Retrieves semantic chunks from SharePoint/OneDrive/Connectors (no LLM) |
| `GET /health` | Health check |

### Adding a Protected Route

Use `Depends(get_graph_token)` for routes that need to call Microsoft Graph, or `Depends(get_current_user)` for routes that only need the user's profile. Both are defined in `app/dependencies.py`.

### Three-way Comparison Design

All three API endpoints share `CopilotChatRequest` as input and `CopilotChatResponse` as output. This is intentional — the frontend comparison panel can call all three routes identically and display results side-by-side.

### Token Cache Architecture Note

The MSAL token cache is **not** stored in the session cookie (too large for ~4 KB cookie limit). Instead, the session cookie holds only a UUID `cache_key`, and the actual serialised cache lives in `app.state.token_cache_store`. This dict is in-memory and does not survive server restarts (acceptable for dev; use Redis or similar in production).
