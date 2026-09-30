# Validation

Validated on Windows build 26200 (25H2), Python 3.12.10, Node 24.14.0, npm 11.9.0.

- `python -m pytest -q`: **135 passed**. One upstream Starlette deprecation warning about its future HTTP test client; no failed tests.
- `npm.cmd run build`: TypeScript and production bundle pass. npm install audit reported zero vulnerabilities.
- Real local Ollama `gemma3:latest`: vague request challenged, specific purpose negotiated, 15-minute access granted through policy/tools, temporary hosts entries removed, early block and usage history verified.
- Headless Microsoft Edge: desktop and mobile rendering, no horizontal overflow, no JavaScript exceptions; starter prompts, chat submission, grant/countdown, completed conversation reload, new request, early block, history, policy screen, mobile navigation, countdown awaiting backend confirmation and offline protection state pass.
- Real-mode launcher rejects non-administrator startup with an actionable message.

All automated filesystem blocking checks used temporary or preview hosts files. The actual Windows hosts file was read but **not modified**. Actual YouTube navigation/blocking needs `Start.cmd` launched as Administrator. Automatic expiry needs the backend running; forced termination cannot enforce a deadline until restart.

See `README.md` for setup, local configuration, runtime limitations and manual hosts recovery.
