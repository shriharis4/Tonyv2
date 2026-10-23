# Tony

Tony is a Windows desktop AI assistant combining voice interaction, agent orchestration, and local desktop automation. It connects to LiveKit for real-time voice sessions and uses Google Gemini for intelligent responses and tool execution.

## Features

- LiveKit-based voice sessions with Gemini Realtime (`gemini-2.5-flash-native-audio-preview`)
- Hybrid keyword router with LLM tool-calling fallback — most commands execute in under 2 seconds
- Hardware echo cancellation so Tony never routes its own voice as a command
- Verified WhatsApp Desktop automation (reads UI controls, confirms contact before sending, never false-reports success)
- File, folder, and app operations — rename/move/copy/delete, zip/unzip, batch rename, content search
- Document authoring: Word (.docx), Markdown, plain text, PowerPoint, Excel
- Real browser automation (Playwright) for forms and navigation
- OCR-based screen interaction (Tesseract, optional)
- Email sending via configured SMTP
- Media, screenshot, Spotify, YouTube, and productivity tools
- PyQt5 desktop HUD
- Structured rotating logs, per-turn latency database (`tony_perf_history.db`), automated test suite

## Requirements

- **Windows 10 or Windows 11**
- **Python 3.12** (64-bit) — [python.org/downloads](https://www.python.org/downloads/)
- **Git**
- A [LiveKit](https://livekit.io) project with `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`
- A [Google AI Studio](https://aistudio.google.com) `GOOGLE_API_KEY` with the Gemini Live API enabled
- **Tesseract OCR** (optional, for screen-text clicking) — [GitHub installer](https://github.com/UB-Mannheim/tesseract/wiki)

## Quick start (new device)

```powershell
# 1 — clone
git clone https://github.com/shriharis4/Tonyv2.git
cd Tonyv2

# 2 — virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip

# 3 — dependencies  (all pinned; ~9 min on first run)
python -m pip install -r requirements.txt

# 4 — browser binaries for browser_automate  (one-time, ~300 MB)
python -m playwright install chromium

# 5 — credentials
Copy-Item .env.example .env
#  open .env and fill in LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET, GOOGLE_API_KEY

# 6 — run
.\.venv\Scripts\python .\main.py
```

## Environment variables

| Variable | Required | Purpose |
|---|---|---|
| `LIVEKIT_URL` | Yes | `wss://your-project.livekit.cloud` |
| `LIVEKIT_API_KEY` | Yes | LiveKit API key |
| `LIVEKIT_API_SECRET` | Yes | LiveKit API secret |
| `GOOGLE_API_KEY` | Yes | Google Gemini Realtime credential |
| `LIVEKIT_AGENT_NAME` | No | Agent name (default `tony`) |
| `USER_NAME` | No | How Tony addresses you (default `Sir`) |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM_EMAIL` | No | Enables `send_email`; missing = clear "not configured" message |

Never commit `.env` — it is already in `.gitignore`.

## Run tests

```powershell
.\.venv\Scripts\python -m pytest tests/ -v
```

All 254 tests run entirely offline (no real mic, network, or desktop actions). They also write to `logs/tony_test.log` so the real latency log is never rotated away during a test run.

## Project structure

| Path | Purpose |
|---|---|
| `main.py` | Entry point |
| `tony.py` | PyQt5 HUD, LiveKit client, audio device setup (AEC) |
| `core/runtime_agent.py` | Agent loop, VAD, router, turn lifecycle, tool wrapper |
| `core/prompts.py` | System and session instructions (English-only output) |
| `core/textnorm.py` | Hindi/Hinglish → English transliterator |
| `core/logging_config.py` | Rotating log setup (respects `TONY_LOG_FILE` env var for tests) |
| `tool_registry.py` | Single source of truth for all 61 tool registrations |
| `tools.py` | Re-exports `tool_registry` |
| `memory_db.py` | SQLite — per-session conversations DB + persistent `tony_perf_history.db` |
| `Tools/` | All automation and productivity tool modules |
| `tests/` | pytest suite (254 tests) |
| `requirements.txt` | Pinned dependencies for a clean install |

## Runtime flow

```
main.py → tony.py → core/runtime_agent.py (agent thread)
                  → livekit client thread (mic + speaker with AEC)
```

**Turn pipeline:** VAD detects speech end → Gemini returns transcript → keyword router tries direct match (< 2 ms) → on match, tool runs via `execute_tool` (tiered timeouts, input lock) → on miss, Gemini native response handles it. Gemini tool calls go through the same lock and are blocked if the router already handled the command, preventing double execution.

## Latency notes

- `speech_to_transcript` (VAD silence → transcript) is the dominant term; it tracks the Gemini Live API round-trip.
- All other stages (router, tool, TTS confirmation) are under 2 s in normal use.
- Per-session timings are written to `tony_perf_history.db` after every turn. Query with `SELECT * FROM turn_timings ORDER BY id DESC LIMIT 20` to see the breakdown.

## Known limitations

- Tesseract OCR binary is not installed automatically; OCR-based screen-click features show a warning at startup until it is added to `PATH`.
- `send_email` requires SMTP credentials in `.env`; missing = graceful "not configured" reply.
- WhatsApp Desktop send requires WhatsApp to be installed as the Microsoft Store app (`WhatsApp.Root.exe`). It reads UI controls to confirm the right contact before sending.

## Security

Never commit `.env`, `service.json`, or `tony_perf_history.db`. All three are already covered by `.gitignore`.

## License

Provided as-is for development and personal use. Review dependency licenses before distributing.
