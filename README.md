# hermes-share

A lightweight, self-hosted companion service for [Hermes Agent](https://hermes-agent.nousresearch.com/) that generates secure, live-updating read-only web links for conversation sessions (CLI, TUI, and Telegram).

Similar to ChatGPT and Claude's "Share Chat", `hermes-share` renders full agent sessions with collapsible reasoning steps, tool invocation inspection, syntax-highlighted code blocks, and real-time Server-Sent Events (SSE) streaming while automatically redacting sensitive credentials.

---

## Architecture

```
 ┌────────────────────────────────────────────────────────┐
 │                      Host Machine                      │
 │  ┌─────────────────────┐      ┌─────────────────────┐  │
 │  │ hermes-gateway/CLI  │      │ ~/.hermes/state.db  │  │
 │  │ (Active Writer)     │─────▶│ (-wal, -shm files)  │  │
 │  └─────────────────────┘      └──────────┬──────────┘  │
 └──────────────────────────────────────────┼─────────────┘
                                            │ hostPath mount / local file
 ┌──────────────────────────────────────────▼─────────────┐
 │               hermes-share Service                     │
 │  ┌──────────────────────────────────────────────────┐  │
 │  │ FastAPI Backend (uv / Python 3.11+)              │  │
 │  │  • Read-only SQLite Reader (PRAGMA query_only)   │  │
 │  │  • Real-time SSE Hub (inotify + delta polling)   │  │
 │  │  • Multi-pass Credential Redaction Engine        │  │
 │  │  • Share Metadata Store (/data/share/share.db)   │  │
 │  └──────────┬────────────────────────────┬──────────┘  │
 │             │                            │             │
 │  ┌──────────▼─────────────┐   ┌──────────▼──────────┐  │
 │  │ REST API & SSE Stream  │   │ Single-Page Web UI  │  │
 │  │ (/api/v1/shares/...)   │   │ (Vite + React)      │  │
 │  └──────────┬─────────────┘   └──────────┬──────────┘  │
 └─────────────┼────────────────────────────┼─────────────┘
               │                            │
               ▼                            ▼
      Public / LAN Viewers            Management API
   (Secret Link: /s/{token})     (CLI & Agent /share hook)
```

### Safe Concurrency & SQLite WAL Reading
Hermes operates SQLite with `PRAGMA journal_mode = WAL;`. `hermes-share` reads from `state.db` using:
- `mode=ro` URI parameter with `PRAGMA query_only = ON;` and `PRAGMA busy_timeout = 5000;`.
- Application-level separation: `hermes-share` never writes to `state.db`. All share tokens, view counts, and expiration metadata are stored in an isolated database (`share.db`).

> [!IMPORTANT]
> In WAL mode, SQLite readers require write permission to the `-shm` file for coordination locks. Ensure the process has read and write permissions in the directory containing `state.db`.

---

## Features

- **High-Entropy Secret Links**: Unguessable 256-bit URL-safe tokens (e.g. `sh_877L4pBy...`).
- **Real-Time Live Updates**: SSE (`text/event-stream`) streams newly appended messages, streaming token deltas, and tool outputs to active viewers with no manual refresh.
- **Automated Secret Redaction**: In-memory recursive masking filters out OpenAI, Anthropic, GitHub, GitLab, Telegram bot tokens, database connection strings, and private keys before payloads leave the server.
- **Privacy & Search Guard**: All share endpoints and HTML views enforce `<meta name="robots" content="noindex, nofollow, noarchive" />` and `X-Robots-Tag: noindex, nofollow, noarchive`.
- **Rich UI**:
  - Clean Dark / Light theme toggle.
  - Collapsible reasoning/thought process blocks with estimated word count.
  - Collapsible tool execution inspectors showing command inputs and truncated stdout.
  - Formatted Markdown with code syntax highlighting and copy-to-clipboard buttons.
- **Link Controls**: Optional TTL duration expiration, instant one-click revocation, and toggleable reasoning visibility.

---

## Quickstart

### 1. Prerequisites

- Python 3.11+ with [`uv`](https://github.com/astral-sh/uv)
- Node.js 22+ with [`pnpm`](https://pnpm.io/) (for building the web UI)

### 2. Local Installation

```bash
git clone https://github.com/theMasix/hermes-share.git
cd hermes-share

# Install Python dependencies and CLI
uv sync
uv tool install --editable .

# Build the frontend assets
cd web
pnpm install
pnpm build
cd ..
```

### 3. Run the Web Server

```bash
hermes-share serve --host 0.0.0.0 --port 8000
```

---

## CLI Usage

The `hermes-share` CLI can interact either directly with the local SQLite databases or remotely over the management API.

```bash
# Share the latest Hermes conversation session
hermes-share create --latest

# Share a specific session ID
hermes-share create 20260918_205722_ec853aff

# Share with a 24-hour expiration
hermes-share create --latest --ttl 24h

# Share without revealing thought/reasoning blocks
hermes-share create --latest --no-reasoning

# Share as a static snapshot (disable live SSE streaming)
hermes-share create --latest --no-live

# Lookup session bound to a specific Telegram topic (chat_id:thread_id)
hermes-share create --telegram-topic "87679709:490031"

# Target a remote hermes-share server
hermes-share create --server http://127.0.0.1:8000 --api-key "your-secret-key" --latest

# List all active share links
hermes-share list

# Revoke a link immediately
hermes-share revoke sh_877L4pBy1tEmqFVJFbCpJaVTLSxkpLom
```

---

## Configuration

The application can be configured via environment variables or a `.env` file:

| Variable | Default | Description |
|---|---|---|
| `HERMES_DB_PATH` | `~/.hermes/state.db` | Absolute or expanded path to Hermes SQLite `state.db`. |
| `SHARE_DB_PATH` | `./share.db` | Path to the metadata SQLite database storing share tokens. |
| `MANAGEMENT_API_KEY` | `default-dev-key` | Secret key required for share creation and revocation. |
| `BASE_URL` | `http://localhost:8000` | Public base URL used when returning generated links. |
| `DEFAULT_TTL_SECONDS` | `0` | Default link expiration in seconds (`0` = indefinite). |
| `REDACT_SECRETS` | `true` | Enables automatic credential and token masking. |
| `HOST` | `0.0.0.0` | Bind IP address for `hermes-share serve`. |
| `PORT` | `8000` | Bind port for `hermes-share serve`. |

---

## API Reference

### Management Endpoints (Requires `X-API-Key`)

- `POST /api/v1/shares` — Create a new share token.
  ```json
  {
    "session_id": "optional-session-id",
    "latest": true,
    "ttl_seconds": 86400,
    "show_reasoning": true,
    "allow_live": true
  }
  ```
- `GET /api/v1/shares` — List all created shares (paginated).
- `DELETE /api/v1/shares/{token}` — Revoke a share token immediately.

### Public Endpoints

- `GET /s/{token}` — Serves the conversation viewer web UI.
- `GET /api/v1/shares/{token}` — Returns redacted session snapshot JSON.
- `GET /api/v1/shares/{token}/stream` — Server-Sent Events stream for real-time turn sync.
- `GET /healthz` — Service health probe.
