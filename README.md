# Tony

Tony is a Windows desktop AI assistant that combines voice interaction, agent orchestration, and local desktop automation. It connects to LiveKit for real-time voice sessions and uses a configured AI provider for intelligent responses and tool execution.

This project includes a desktop UI, an agent runtime, prompt management, and a collection of Windows automation tools for tasks such as file handling, browser interaction, messaging, scheduling, document work, screenshots, app launching, and system actions.

## Features

- LiveKit-based voice sessions
- Real-time AI assistant runtime
- Desktop automation tools for Windows
- File, folder, and app operations
- Browser search and content interaction helpers
- Media, screenshot, and productivity utilities
- Local SQLite memory storage
- PyQt-based desktop interface

## Requirements

Before running the project, make sure you have:

- Windows 10 or Windows 11
- Python 3.12
- Git
- A LiveKit project and valid credentials
- API/model credentials for the configured AI provider
- Desktop automation permissions for Windows actions

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

## Configure environment variables

Create a local environment file:

```powershell
Copy-Item .env.example .env
```

Then update `.env` with the required values for your LiveKit and AI provider setup. Do not commit `.env` to Git.

Typical configuration values may include:

- LiveKit URL and token settings
- AI provider API key
- Model selection
- Any service credentials required by the tools

## Run the app

Start the project with:

```powershell
.\.venv\Scripts\python .\main.py
```

This launches the desktop assistant and starts the runtime agent flow.

## Project structure

- `main.py` — application entry point
- `tony.py` — PyQt interface and app startup logic
- `core/runtime_agent.py` — runtime agent and tool registration
- `core/prompts.py` — system and session prompt definitions
- `core/agent.py` — core agent exports
- `Tools/` — automation and productivity tool modules
- `memory_db.py` — local memory database logic
- `requirements.txt` — Python dependencies
- `livekit.toml` — LiveKit configuration

## Runtime flow

The main execution path is:

```text
main.py -> tony.py -> core/runtime_agent.py
```

The runtime agent is responsible for connecting the UI, the voice session, and the tool layer.

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

## Security note

Never commit secrets, API keys, or local runtime data to Git. Keep `.env` and any sensitive credentials outside the repository whenever possible.

## License

This project is provided as-is for development and personal use. If you plan to distribute or deploy it, review any dependency or service license requirements before doing so.

