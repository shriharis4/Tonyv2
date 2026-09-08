# Tony

Tony is a Windows-focused voice and desktop assistant. It connects to LiveKit for voice sessions, uses the configured realtime model, and exposes tools for desktop control, communication, media, documents, screenshots, scheduling, and productivity tasks.

## Prerequisites

- Windows is the supported platform because desktop automation and `pywin32` integrations are used.
- Python 3.12 is the tested interpreter for this workspace.
- LiveKit credentials and the model/API credentials required by the tools.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Fill `.env` with the real values. Never commit `.env`, API keys, passwords, or Firebase service-account files. Firebase credentials must be supplied through `FIREBASE_SERVICE_ACCOUNT_JSON` or `GOOGLE_APPLICATION_CREDENTIALS` pointing outside this repository. Voice enrollment remains an explicit local setup step through `enroll_user.py` when that feature is required.

## Run

```powershell
.\.venv\Scripts\python .\main.py
```

The canonical path is `main.py` -> `tony.py` -> `core/runtime_agent.py`. The existing PyQt UI implementation remains in `tony.py`; its layout, styling, widgets, and animation behavior were preserved while identity labels were updated.

## Structure

- `main.py`: single desktop entry point
- `tony.py`: existing PyQt presentation and startup wiring
- `core/runtime_agent.py`: LiveKit agent, routing, and tool registration
- `core/prompts.py`: canonical Tony system and session prompts
- `core/agent.py`: core agent export
- `Tools/`: action-specific tool modules
- `auth/` functionality: current voice authentication modules remain at the project root until their deployment contract is confirmed
- `docs/ARCHITECTURE.md`: component and runtime flow

## What changed from MJ/Nova

The active implementation now has Tony as its canonical identity and entrypoint. Duplicate Nova voice/UI implementations, duplicate prompt definitions, duplicate memory modules, obsolete build specs, scratch scripts, and Python caches were removed after checking that they were not reachable from the active entrypoint. Credentials were removed from source and moved to environment-variable lookups. Direct command routing and executor-based desktop/TTS operations remain on the existing hot path; no UI layout or styling rewrite was performed.

See `CHANGES.md` for the explicit deletion and consolidation report.
