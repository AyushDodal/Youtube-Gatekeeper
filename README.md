# YouTube Gatekeeper

A Windows-only, local-first attention guard. YouTube is blocked by default. Ask **The Gatekeeper** for access, explain your purpose, and negotiate a time limit. A local Ollama model recommends an action; deterministic Python policy decides whether it is permitted.

React + TypeScript + Vite → FastAPI → Ollama / policy engine → session manager → Windows hosts file. SQLite stores conversations, access sessions and usage. No cloud LLM API, Docker, telemetry, background installation or automatic elevation.

## Quick start on this laptop

Python 3.12 and Node 24 were detected. Ollama is already serving `gemma3:latest` on port 11434; the ignored local `.env` selects it. Model choice is configurable and is not embedded in application code.

1. Run `Setup.cmd` to install Python dependencies in `.venv`, install frontend dependencies, and build the UI.
2. Right-click `Start.cmd` and choose **Run as administrator**. Windows requires this for the hosts file. The launcher never elevates itself.
3. Open **http://127.0.0.1:8000**. Keep the terminal running. YouTube should show **Blocked** after successful hosts modification.
4. Explain what you want to watch and why. A valid grant creates a countdown; expiry re-blocks automatically. **End session** returns to blocking early.
5. **Usage history** shows past sessions and the last seven days of access time.

For a harmless walkthrough, use `Start-preview.cmd`. Its visible **Simulation** banner means no system blocking occurs. Preview hosts and database files are separate from production state.

## Fresh Windows setup

Install [Python 3.11+](https://www.python.org/downloads/windows/) (enable “Add python.exe to PATH”), [Node.js](https://nodejs.org/en/download), and [Ollama for Windows](https://ollama.com/download/windows). Confirm:

```powershell
python --version
node --version
npm.cmd --version
ollama --version
ollama list
```

Download a local model that fits your machine. For example, `ollama pull gemma3:4b`. This example downloads several GB; it is not a required or hardcoded model. Start Ollama from its installed app, or run `ollama serve` if no server is already running. Set `OLLAMA_MODEL` to the exact name shown by `ollama list`.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
cd frontend
npm.cmd ci
npm.cmd run build
cd ..
```

Edit `.env` before starting. Existing environment variables override `.env`. `npm.cmd` works even when PowerShell blocks the unsigned `npm.ps1` shim; virtual-environment activation is unnecessary.

## Configuration

```dotenv
OLLAMA_MODEL=your-installed-model:tag
OLLAMA_BASE_URL=http://127.0.0.1:11434
GATEKEEPER_DRY_RUN=false
```

The Ollama URL must be loopback HTTP. An unset model or unavailable Ollama produces a clear setup error and cannot grant access. Models must produce structured JSON; invalid output is rejected. The provider interface is in `backend/llm/base.py`, with the default implementation in `ollama_provider.py`.

Edit `config.yaml` and restart the backend to change limits:

```yaml
youtube:
  min_session_minutes: 5
  max_session_minutes: 60
  daily_limit_minutes: 120
gatekeeper:
  max_question_rounds: 8
```

The minimum may not be lower than five minutes. A grant needs a reason and a whole-number duration within the configured bounds. The full requested duration must fit the remaining daily allowance. Active sessions cannot be extended. The conversation has a finite number of question rounds, after which it must reach a decision. Model instructions cannot override these rules.

Optional `GATEKEEPER_CONFIG_PATH` and `GATEKEEPER_DATABASE_PATH` set project-relative or absolute paths. The defaults are `config.yaml` and `data/gatekeeper.sqlite3`; preview uses `data/preview.sqlite3` and `data/hosts.preview`. Keep `.env` and databases private. Conversation text stays on this machine.

## Development

Run one backend process, **one worker**, on loopback. In an Administrator terminal for actual blocking:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

In a second, ordinary terminal:

```powershell
cd frontend
npm.cmd run dev
```

Open http://127.0.0.1:5173. Vite proxies `/api` to FastAPI. For simulation, set `$env:GATEKEEPER_DRY_RUN = 'true'` before starting the backend. Avoid reload/multiple workers during real access sessions. A built UI is served directly by FastAPI, so normal use needs only `Start.cmd`.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest
cd frontend
npm.cmd run build
```

Tests use temporary hosts files and SQLite databases; they never touch Windows hosts. Ollama is mocked for deterministic API tests. Coverage includes idempotent hosts edits, preservation of unrelated bytes, malformed sections, permissions, rejected durations, daily limits, expiry, restart recovery, failed unlocks, malformed model JSON, overlong grants, and API validation. No live model is required for this suite.

Optional integration checks:

```powershell
# Real configured Ollama model, with temporary hosts and database files only:
.\.venv\Scripts\python.exe scripts/check_model.py
# UI checks require Start-preview.cmd running and Microsoft Edge installed:
.\.venv\Scripts\python.exe -m pip install -r requirements-browser.txt
.\.venv\Scripts\python.exe scripts/inspect_ui.py
.\.venv\Scripts\python.exe scripts/check_ui.py
```

The UI regression check supplies isolated API fixtures in its browser context to exercise grants, reloads, early blocking, countdown confirmation, offline errors, history and mobile navigation. This does not grant real access or change production data. Screenshots are saved under `artifacts/`.

## API and tools

| Endpoint | Behavior |
| --- | --- |
| `GET /api/status` | Actual managed hosts state, exact expiry, errors, model health and policy |
| `POST /api/chat` | `{ "message": "...", "conversation_id": "optional existing ID" }` |
| `GET /api/conversations/{id}` | Restore persisted conversation messages |
| `GET /api/session` | Current session or `null` |
| `GET /api/usage` | Today's usage, allowance, recent sessions and daily totals |
| `POST /api/admin/block` | End access early and re-block; JSON `{}` body |

There is no unlock endpoint. Chat returns `response`, `decision`, `conversation_id`, `youtube_status`, and tool events. The fixed tool registry includes `check_youtube_status`, `grant_youtube_access`, and `deny_youtube_access`. Only validated structured decisions reach those tools. There is no execution of model-generated Python or shell commands. Mutations require JSON and an allowed local origin; unknown Host headers are rejected. This is a personal local app, not a multi-user service.

## Expiry, restarts, and usage semantics

Grants are committed to SQLite **before** removing the block, including start time, exact UTC expiry, duration and reason. The expiry loop runs independently of model inference. If an active session is restored before expiry, it retains its original deadline. If restored after expiry, YouTube is blocked immediately. A failed hosts operation is shown as an error; the UI never claims successful protection when the backend cannot confirm it.

**Keep the backend running to enforce deadlines.** The scheduler normally checks once a second. Graceful shutdown attempts to re-block while preserving the session's original deadline for restart. If the process is killed, Windows shuts down, or the machine is asleep, Python cannot run an expiry action. The correct state is reconciled on restart/resume. This version installs no Windows service, scheduled task or hidden watchdog; it cannot promise blocking while terminated.

Usage measures **permitted access time**, not actual watching or browser activity. Early-ended sessions count only elapsed time. Sessions spanning local midnight are split between days; timestamps are stored in UTC and displayed locally. History is limited to the latest 100 sessions, while daily allowance calculations include all stored sessions. A crashed session is conservatively accounted through its expiry unless it was ended early.

## Hosts file behavior and recovery

Default path: `C:\Windows\System32\drivers\etc\hosts` (uses `%SystemRoot%` if Windows is installed elsewhere). The controller maps `youtube.com`, `www.youtube.com`, `m.youtube.com`, `youtu.be`, and `www.youtu.be` to `127.0.0.1` inside exactly one managed section:

```text
# === YOUTUBE_GATEKEEPER_START ===
127.0.0.1 youtube.com
127.0.0.1 www.youtube.com
127.0.0.1 m.youtube.com
127.0.0.1 youtu.be
127.0.0.1 www.youtu.be
# === YOUTUBE_GATEKEEPER_END ===
```

Everything outside the section is preserved. The controller uses locked, in-place edits, avoids duplicate entries and refuses damaged/duplicate markers. On an I/O failure it attempts rollback. On successful changes it runs the fixed Windows `ipconfig /flushdns` command. A small metadata comment inside the section may record an added separator newline to restore original bytes exactly.

To manually restore access or uninstall:

1. Stop the backend first so it cannot reapply the section.
2. Start Notepad **as Administrator**, choose **File → Open**, choose **All files**, and open the hosts path above.
3. Delete only the lines from `# === YOUTUBE_GATEKEEPER_START ===` through `# === YOUTUBE_GATEKEEPER_END ===`, inclusive. Preserve all other entries. Save without a `.txt` extension.
4. Run `ipconfig /flushdns` in an Administrator terminal and close/reopen your browser if needed.
5. The project folder and local databases may then be removed. No system service or startup task needs uninstalling.

This is psychological friction, not a security boundary. Hosts files do not support wildcard domains; alternate domains, VPN/proxy behavior, DNS choices and already-established browser connections can bypass or delay the effect. Existing video streams may continue. Close old YouTube tabs and check a new navigation when testing. Other blockers' hosts entries are intentionally preserved and can keep YouTube blocked during an approved session.

## Implementation references

The integration follows Ollama's [structured outputs](https://ollama.com/blog/structured-outputs) JSON-schema interface and FastAPI's [lifespan](https://fastapi.tiangolo.com/advanced/events/) mechanism for startup reconciliation and the expiry task.
