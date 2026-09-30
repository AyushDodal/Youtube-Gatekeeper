# YouTube Gatekeeper

> **YouTube is blocked. Convince Big Bro to let you in.**

YouTube Gatekeeper is a **local-first AI attention guard for Windows**. Instead of treating YouTube access as a one-click decision, it makes you explain what you want to watch, why you want to watch it, and how long you actually need.

A local Ollama model plays **Big Bro** — a skeptical, sarcastic older-brother-style gatekeeper. But the LLM never gets the final say:

**LLM recommends → deterministic policy decides → fixed tool executes.**

Everything runs locally. No cloud LLM API, telemetry, Docker, or background service.

## Demo

**Watch the demo:** *YouTube Gatekeeper in action — from blocked → negotiation → temporary access → automatic re-blocking.*

> The demo video is included with this project. If you are viewing the repository on GitHub, open the repository's video attachment to watch it.

## Why?

Most website blockers rely on willpower or a simple switch:

> "Do you really want to open YouTube?"  
> **Yes.**

That's not much friction.

Gatekeeper turns the decision into a conversation.

> **You:** I need YouTube for research.  
> **Big Bro:** What exactly are you researching?  
> **You:** Machine learning.  
> **Big Bro:** And why YouTube?  
> **You:** I need to follow a 20-minute tutorial.  
> **Big Bro:** Much better. That's a reason. Not "I accidentally opened YouTube and somehow ended up watching dogs for an hour."

The goal isn't to ban entertainment. It's to make the choice **intentional**.

## How it works

```text
                    ┌─────────────────┐
                    │   User request  │
                    └────────┬────────┘
                             ↓
                    ┌─────────────────┐
                    │   Big Bro / LLM │
                    │     Ollama      │
                    └────────┬────────┘
                             ↓
                    Structured JSON
                             ↓
              ┌──────────────────────────┐
              │   Deterministic Policy   │
              │         Engine           │
              └────────────┬─────────────┘
                           ↓
                    ┌───────────────┐
                    │ Fixed Tool    │
                    │    Registry   │
                    └───────┬───────┘
                            ↓
                  ┌───────────────────┐
                  │ Windows hosts file│
                  └───────────────────┘
```

The important architectural boundary is that **the model is not trusted with permissions**.

The model can recommend:

- `continue_questioning`
- `deny`
- `grant`

The backend validates the structured response and applies deterministic rules for duration, daily allowance, active sessions, and other constraints before anything touches the hosts file.

There is **no model-generated Python, shell command, or arbitrary tool execution**.

## What happens when access is granted?

1. The request is persisted to SQLite.
2. The backend validates the requested duration against policy.
3. YouTube is temporarily unblocked.
4. A countdown tracks the exact expiry.
5. The expiry task re-blocks YouTube automatically.
6. Ending the session early blocks it immediately.
7. Usage is recorded locally.

The backend owns the deadline — not the LLM.

## Features

- 🤖 **Local AI gatekeeper** powered by Ollama
- 🧠 **Conversational friction** instead of a simple allow/deny button
- 🔒 **Blocked by default**
- ⏱️ **Bounded access sessions** with automatic expiry
- 📊 **Local usage history** and daily allowance
- 🛡️ **Deterministic policy enforcement**
- 🏠 **Fully local** — conversations and usage stay on the machine
- 🪟 **Windows hosts-file control**
- 🧪 **Simulation mode** for development without modifying the real hosts file
- ⚡ **React + TypeScript + Vite** frontend
- 🚀 **FastAPI** backend
- 🗄️ **SQLite** persistence

## Security model

The LLM is treated as an **untrusted decision recommender**, not an authority.

Several layers enforce this:

- Structured JSON responses are validated with strict Pydantic models.
- Unknown JSON fields and duplicate keys are rejected.
- Grant durations must be whole integers.
- Session limits and daily limits are enforced outside the model.
- Active sessions cannot be extended.
- The tool registry is fixed in application code.
- Model output cannot execute code or shell commands.
- Ollama is restricted to a local loopback address.
- Hosts-file changes are isolated to the Gatekeeper-owned section.
- Failed writes attempt rollback.
- Existing hosts-file entries outside the managed section are preserved.
- Local API mutations require the expected local request headers/origin.

This is an **attention-management tool, not a security boundary**. Hosts-file blocking can be bypassed by things such as VPNs, proxies, alternate domains, DNS configuration, or existing browser connections.

## Architecture

```text
React / TypeScript / Vite
          │
          │ /api
          ▼
       FastAPI
          │
    ┌─────┴──────────┐
    │                │
    ▼                ▼
Gatekeeper       Session Manager
   Agent              │
    │                 ▼
    ▼              SQLite
Ollama
    │
    ▼
Structured decision
    │
    ▼
Policy Engine
    │
    ▼
Fixed Tool Registry
    │
    ▼
YouTube Controller
    │
    ▼
Windows hosts file
```

## Configuration

Copy `.env.example` to `.env` and configure a locally installed Ollama model:

```dotenv
OLLAMA_MODEL=your-installed-model:tag
OLLAMA_BASE_URL=http://127.0.0.1:11434
GATEKEEPER_DRY_RUN=false
```

Session policy lives in `config.yaml`:

```yaml
youtube:
  min_session_minutes: 5
  max_session_minutes: 60
  daily_limit_minutes: 120

gatekeeper:
  max_question_rounds: 8
```

The model is configurable and is **not hardcoded into the application**.

## Run it

### Requirements

- Windows
- Python 3.11+
- Node.js
- Ollama
- A local Ollama model

### Setup

Run:

```text
Setup.cmd
```

Then set `OLLAMA_MODEL` in `.env`.

For the real application, run:

```text
Start.cmd
```

as Administrator. Windows requires administrator privileges to modify the hosts file.

For a safe walkthrough without modifying system networking:

```text
Start-preview.cmd
```

Preview mode uses isolated hosts/database files and clearly indicates that it is running in simulation mode.

## Development

Run the backend on loopback:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Run the frontend separately:

```powershell
cd frontend
npm.cmd run dev
```

The Vite development server proxies `/api` to FastAPI.

For real access sessions, run **one backend worker** and keep the backend running. The expiry loop cannot enforce a deadline while the process itself is stopped.

## Testing

```powershell
.\.venv\Scripts\python.exe -m pytest

cd frontend
npm.cmd run build
```

The test suite uses temporary hosts files and SQLite databases. It does not modify the Windows hosts file.

Coverage includes:

- hosts-file idempotency
- preservation of unrelated entries
- malformed managed sections
- permissions failures
- rejected durations
- daily limits
- session expiry
- restart recovery
- failed unlocks
- malformed model responses
- overlong grants
- API validation

No live LLM is required for the test suite.

## API

| Endpoint | Purpose |
| --- | --- |
| `GET /api/status` | Blocking state, expiry, model health and policy |
| `POST /api/chat` | Send a Gatekeeper message |
| `GET /api/conversations/{id}` | Restore a conversation |
| `GET /api/session` | Current access session |
| `GET /api/usage` | Usage, allowance and history |
| `POST /api/admin/block` | End access and re-block YouTube |

There is deliberately **no unlock endpoint**. Access must go through the Gatekeeper conversation.

## Hosts-file behavior

The controller manages one dedicated section of the Windows hosts file:

```text
# === YOUTUBE_GATEKEEPER_START ===
127.0.0.1 youtube.com
127.0.0.1 www.youtube.com
127.0.0.1 m.youtube.com
127.0.0.1 youtu.be
127.0.0.1 www.youtu.be
# === YOUTUBE_GATEKEEPER_END ===
```

Everything outside this section is preserved.

When access ends, the managed section is removed and DNS is flushed.

If you need to manually restore the hosts file, stop the backend first and remove only the Gatekeeper section.

## Project structure

```text
backend/
├── agents/       # LLM decision layer
├── api/          # FastAPI routes
├── llm/          # Local LLM provider
├── services/     # Policy, sessions and YouTube control
├── tools/        # Fixed application tool registry
└── main.py       # Application entry point

frontend/
├── components/
├── hooks/
├── pages/
└── services/

scripts/           # Model/UI integration checks
config.yaml        # Deterministic policy configuration
Setup.cmd          # Windows setup
Start.cmd          # Production launcher
Start-preview.cmd  # Safe simulation launcher
```

## Design principle

The interesting part of this project isn't blocking YouTube.

It's the separation between **reasoning and authority**.

The LLM gets to reason about the user's request.

It does **not** get to decide what the computer is allowed to do.

> **The model recommends.  
> The application decides.  
> The tools execute.**

That's the pattern this project is built around.
