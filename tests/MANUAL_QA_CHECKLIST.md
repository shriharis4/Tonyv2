# Manual QA Checklist (Real Windows Device)

The automated suite in `tests/` covers router logic, timeout tiering,
structured results, tool registration, and new coverage tools using mocks.
The rows below require a real Windows 10/11 machine with a working
microphone, LiveKit credentials, and the target applications installed —
they cannot be safely or meaningfully run in CI. Run these manually before
calling a build release-ready, per the spec's full test matrix.

For each row: record latency (stopwatch or GUI diagnostics panel) and
pass/fail, and compare against a commercial assistant (Google Assistant /
Siri) where noted in the spec as the comparison benchmark.

| # | Category | Command to test | Pass criteria |
|---|----------|-----------------|----------------|
| 1 | App launch | "Open Chrome" / "Start VS Code" / "Khol notepad" | Correct app opens within 1.5s; Hindi/Hinglish phrasing matches too |
| 2 | App close | "Close Spotify" / "Exit Excel" | Correct app closes, no other window affected |
| 3 | Window mgmt | "Minimize this" / "Maximize the window" | Active window only, not a random one |
| 4 | Volume/brightness | "Turn the volume up" / "Set brightness to 40" | Exact numeric change applied; relative vs absolute both work |
| 5 | File create | "Create a folder called Project X on the desktop" | Folder exists at correct path with exact name |
| 6 | Document write | "Write a one-paragraph summary about renewable energy in a Word document" | Real .docx created with the content |
| 7 | Document edit | "Open my resume and change the phone number to 555-0100" | Correct file found, correct text replaced, saved |
| 8 | Spreadsheet | "Put 500, 300, 200 into column A rows 1-3 in Excel and sum them" | Values land in correct cells; sum correct |
| 9 | PDF | "Open the invoice PDF and read me page 2" | Correct file found by fuzzy match; correct page read aloud |
| 10 | File conversion | "Convert this Word doc to PDF" | Output PDF created next to source, opens correctly |
| 11 | Web search | "Search the web for the capital of Peru" | Factually correct answer spoken back |
| 12 | Browser interaction | "Go to gmail.com and open my inbox" | Page navigates/loads; graceful message if login required |
| 13 | Messaging | "WhatsApp Raj saying I'll be 10 minutes late" | Correct contact resolved, correct message sent |
| 14 | Email | "Email my manager the weekly report is attached" | Email sends via configured provider, or clear "not configured" message |
| 15 | Media | "Play Shape of You on Spotify" / "Play relaxing music on YouTube" | Correct track/search plays |
| 16 | Screenshot/vision | "Take a screenshot" / "What's on my screen right now" | Screenshot saved; description matches actual screen |
| 17 | Reminders | "Remind me to call the dentist at 5 PM" | Reminder fires at correct time with correct text |
| 18 | Scheduling | "Every weekday at 9 AM open my email" | Task persists across restarts and fires on schedule |
| 19 | System power | "Shut down the computer" | Requires explicit confirmation before executing; near-zero false positive rate |
| 20 | System info | "How much battery do I have left" / "What's my CPU usage" | Numbers match actual OS values |
| 21 | Security | "Scan my computer for viruses" | Scan runs, result reported accurately |
| 22 | Multi-step | "Open Chrome, then search for weather in Mumbai, then take a screenshot" | All 3 steps execute in order; dependent steps wait for prior app readiness |
| 23 | Interruption | New command mid-response | Old turn cleanly cancelled, no overlapping speech/duplicate execution |
| 24 | Ambiguous input | "Open it" with no prior context | Tony asks "open what?" rather than guessing |
| 25 | Unsupported request | "Defragment my hard drive" | Clear, honest decline message, never a crash or wrong tool |
| 26 | Multilingual | Same commands in Hindi/Hinglish | Equivalent accuracy and latency to English phrasing |
| 27 | Network loss | Gemini API unreachable mid-session | Direct commands still work; clear spoken notice, no hang |
| 28 | Stress/rapid-fire | 5 commands back-to-back with no pause | No turn corruption, no dropped/duplicate execution |

## Pre-flight before running these

1. `pip install -r requirements.txt`
2. `playwright install chromium` (for browser automation row #12)
3. Fill in `.env` with real LiveKit + Gemini credentials (see `.env.example`)
4. For row #14 (email), set `SMTP_HOST`/`SMTP_PORT`/`SMTP_USERNAME`/`SMTP_PASSWORD` in `.env`, or confirm the "not configured" message appears instead
5. Run `python main.py` and speak each command naturally; do not type unless specifically testing text input
