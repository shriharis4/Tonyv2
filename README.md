# Tony

Tony is a Windows desktop AI assistant that combines voice interaction, agent orchestration, and local desktop automation. It connects to LiveKit for real-time voice sessions and uses a configured AI provider for intelligent responses and tool execution.

This project includes a desktop UI, an agent runtime, prompt management, and a collection of Windows automation tools for tasks such as file handling, browser interaction, messaging, scheduling, document work, screenshots, app launching, and system actions.

## Features

- LiveKit-based voice sessions
- Real-time AI assistant runtime with a hybrid keyword router + LLM tool-calling fallback
- Tiered timeouts and structured success/failure results on every tool call
- Rotating structured logs (`logs/tony.log`, `logs/routing_accuracy.log`) instead of console-only output
- Retry-with-backoff and graceful degraded mode when the AI engine is unreachable
- Destructive-action confirmation gating (shutdown/restart/hibernate, file deletion)
- Desktop automation tools for Windows
- File, folder, and app operations — including rename/move/copy/delete, zip/unzip, batch rename, and content search
- Document authoring and editing: real Word (.docx), Markdown, and plain-text files; PowerPoint slide creation/editing
- Excel formula entry and chart creation, beyond basic cell data entry
- Real browser automation (Playwright) for navigating and filling forms, in addition to web search/scraping
- Email sending via configured SMTP
- OCR-based "click the X button" vision-guided clicking, wired into the general desktop-action fallback
- Media, screenshot, and productivity utilities
- Local SQLite memory storage with schema versioning and corruption recovery
- PyQt-based desktop interface
- Automated test suite (`pytest`, see `tests/`)

## Requirements

Before running the project, make sure you have:

- Windows 10 or Windows 11
- Python 3.12
- Git
- A LiveKit project and valid credentials
- API/model credentials for the configured AI provider
- Desktop automation permissions for Windows actions
- (Optional) SMTP credentials if you want `send_email` to actually send mail
- (Optional) Tesseract OCR installed and on PATH for OCR-based screen-text/click features

## Clone the project

```powershell
git clone https://github.com/shriharis4/Tonyv2.git
cd Tonyv2
```

## Set up the environment

Create a virtual environment and install dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Browser automation (`browser_automate`) uses Playwright, which needs its
browser binaries installed once after `pip install`:

```powershell
playwright install chromium
```

## Configure environment variables

Create a local environment file:

```powershell
Copy-Item .env.example .env
```

Then update `.env` with the required values for your LiveKit and AI provider setup. Do not commit `.env` to Git.

Environment variables used by the app:

| Variable | Required | Purpose |
| --- | --- | --- |
| `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET` | Yes | LiveKit voice session connection |
| `LIVEKIT_AGENT_NAME` | No | Agent name registered with LiveKit (defaults to `tony`) |
| `GOOGLE_API_KEY` | Yes (for Gemini Realtime) | AI provider credential |
| `GROQ_API_KEY`, `OPENAI_API_KEY` | No | Used by specific tools (e.g. code-fix helper) if configured |
| `USER_NAME` | No | How Tony addresses you (defaults to `Sir`) |
| `TONY_VARIANT`, `LAN` | No | Persona/language variant selection |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM_EMAIL` | No | Enables `send_email`. If any are missing, the tool returns a clear "email isn't configured" message instead of failing silently |

## Run the app

Start the project with:

```powershell
.\.venv\Scripts\python .\main.py
```

This launches the desktop assistant and starts the runtime agent flow.

## Running tests

The project includes an automated test suite covering the direct router
(including word-boundary intent matching and destructive-action
confirmation gating), tool timeout tiering, the structured result
contract, tool registry de-duplication, the new coverage tools, and
Gemini retry/degraded-mode behavior. Everything is mocked — no real
desktop actions, network calls, or file deletions occur.

```powershell
python run_tests.py
```

or directly with pytest:

```powershell
pytest tests/ -v
```

Some test-matrix rows (real voice I/O, real Spotify/WhatsApp automation,
real system power actions, real virus scans, Hindi/Hinglish voice parity,
network-loss degradation on real hardware) require a physical Windows
machine with LiveKit connected and cannot be safely run in CI — see
`tests/MANUAL_QA_CHECKLIST.md` for that checklist.

## Project structure

- `main.py` — application entry point
- `tony.py` — PyQt interface and app startup logic
- `core/runtime_agent.py` — runtime agent, direct router, and tool execution/timeout/logging logic
- `core/prompts.py` — system and session prompt definitions, including the tool-calling manifest
- `core/logging_config.py` — rotating structured logging setup
- `core/agent.py` — core agent exports
- `tool_registry.py` — single source of truth for tool registration; both `tools.py` and `core/runtime_agent.py` import from here
- `tools.py` — thin facade re-exporting `tool_registry`
- `Tools/` — automation and productivity tool modules
- `memory_db.py` — local SQLite memory database with schema versioning
- `tests/` — automated test suite (pytest) and manual QA checklist
- `run_tests.py` — one-command test runner
- `requirements.txt` — Python dependencies
- `livekit.toml` — LiveKit configuration

## Runtime flow

The main execution path is:

```text
main.py -> tony.py -> core/runtime_agent.py
```

The runtime agent is responsible for connecting the UI, the voice session, and the tool layer. Each voice turn first tries the direct keyword router (fast path, no network round trip); if nothing matches, it falls through to the Gemini Realtime model with retry-with-backoff and a graceful degraded mode if the AI engine is unreachable.

## Logs & diagnostics

Structured logs are written to `logs/tony.log` (rotating, 5MB x 5 backups) and `logs/routing_accuracy.log` (every transcript → matched intent → tool → result tuple, for offline accuracy review). These are gitignored and created automatically on first run.

## Troubleshooting

### Virtual environment is not active
Use:

```powershell
.\.venv\Scripts\Activate.ps1
```

### Dependencies do not install
Make sure you are using Python 3.12 and that your virtual environment is activated before running pip.

### Credentials are missing
Check your `.env` file and confirm all required LiveKit and AI provider values are present.

### Windows automation does not work
Some actions may require user interaction, desktop accessibility permissions, or admin access depending on your Windows configuration.

### Browser automation fails with a Playwright error
Run `playwright install chromium` after installing requirements.

### Email sending says "not configured"
Set `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, and `SMTP_PASSWORD` in `.env`.

## Security note

Never commit secrets, API keys, or local runtime data to Git. Keep `.env` and any sensitive credentials outside the repository whenever possible.

## License

This project is provided as-is for development and personal use. If you plan to distribute or deploy it, review any dependency or service license requirements before doing so.


