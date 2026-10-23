# Tony v2 — Session Handoff & Progress Log

**Last updated:** 2026-10-23 (session end)
**Repo:** `C:\Users\DELL\Desktop\MJ` (GitHub: `shriharis4/Tonyv2`, branch `main`)
**Reference:** the original fast assistant is at `C:\Users\DELL\Desktop\Projects\TONNY_1\MJ\MJ\mj original` (named "MJ/Nova") — use it to compare for latency ideology, do NOT copy it back wholesale.

---

## 0. HARD CONSTRAINTS (carry forward every session)

- **DO NOT modify `tony.py`** (the PyQt HUD/UI) — layout, styling, animations, widgets are frozen. Only non-visual wiring is allowed, and we avoided touching it entirely this session.
- **DO NOT touch `Tony_Ultimate_Presentation.pptx`** (user instruction early in the project).
- Keep LiveKit + Gemini Live as the voice pipeline; keep `core/prompts.py` persona (female "Tony"); keep `Tools/` layout and SQLite memory.
- No secrets in source — everything from `.env` (which is gitignored; `.env.example` exists as the template).
- Windows 10/11, Python 3.12, venv at `.venv`.

---

## 1. HOW TO RUN / TEST

```powershell
cd C:\Users\DELL\Desktop\MJ
.\.venv\Scripts\python.exe -m pytest tests/ -q      # full suite (202 tests, all pass)
.\.venv\Scripts\python.exe run_tests.py             # one-command runner
.\.venv\Scripts\python.exe .\main.py                # launch the app (needs .env + mic)
```

Logs: `logs/tony.log` (rotating, all print() output) and `logs/routing_accuracy.log`
(transcript->intent->tool->result). Per-turn timing is persisted to the
`turn_timings` table in `tony_memory.db` and printed as `[PERF]` lines.

**Shell note:** this environment's PowerShell mangles non-ASCII console output
(cp1252) and `&&` isn't valid. Use `;` to chain, and write test output to a
UTF-8 file + read it back when checking Indic/emoji strings. AVOID em-dash/
smart-quote chars inside `print()`/f-strings in `core/runtime_agent.py` — the
custom Unicode-safe print wrapper + console encoding can silently truncate
output (cost hours of false "hang" debugging early on). Use plain ASCII.

---

## 2. CURRENT STATE (as of session end)

- **202 automated tests, all passing** (up from 0 at project start, 108 mid-session).
- `core/runtime_agent.py` is the live runtime agent (~2000+ lines). `main.py` -> `tony.py` -> `core/runtime_agent.py`.
- Architecture: LiveKit AgentSession + Gemini Realtime. Each voice turn: STT ->
  `normalize_transcript` -> direct keyword router (`route_command_directly`) ->
  if miss, Gemini's NATIVE turn answers (no second round-trip anymore).

---

## 3. WHAT WAS DONE THIS SESSION (chronological, by theme)

### 3.1 Foundational upgrades (from the first two spec docs)
- **`tool_registry.py`** (NEW): single source of truth for all tool imports; both
  `tools.py` and `core/runtime_agent.py` import from it. Exposes `TOOL_CATEGORY`,
  `get_tool_timeout()`, `get_all_tool_functions()`, and `get_tool_by_name()`.
- **`tools.py`**: rewritten to re-export from `tool_registry` (dedup — fixes the
  "tool in one list but not the other" hazard).
- **`core/prompts.py`**: rewrote `AGENT_INSTRUCTION_FOR_TOOLS` to match real
  `Tools/` signatures (removed phantom tools `get_system_info()`, `say_reminder`,
  `load_and_analyze_excel()`, `create_visualizations()`); fixed stale `memory.json`
  mention; removed dead `get_readable_chat_history_v2()`.
- **`execute_tool()`**: wrapped every tool in `asyncio.wait_for` with tiered
  timeouts via `get_tool_timeout` — in_process 2s / app_launch 8s / network 15s /
  **ui_automation 25s** (added so Spotify/WhatsApp keyboard flows aren't cut off).
  Never raises — returns structured `fail()` strings. Crash isolation.
- **`core/logging_config.py`** (NEW): `get_logger()` (rotating file) +
  `log_turn_outcome()`.
- **`Tools/tool_result.py`** (NEW): `ok()/fail()/is_failure()` structured result
  contract (`{ok, message, detail}` rendered as "✅ .."/"❌ ..").
- **`memory_db.py`**: schema versioning (now **v2**), corruption recovery
  (PRAGMA integrity_check -> back up corrupt file -> fresh DB, fully fail-safe),
  added `turn_timings` table + `log_turn_timing()`/`get_recent_timings()`.
- **`_run_startup_self_check()`**: verifies LiveKit creds, Gemini reachability
  (`is_network_reachable()` live socket check), Tesseract/OCR presence at startup.
- **`_generate_reply_with_retry()`** + degraded-mode notice (retry once w/ backoff).
  NOTE: this is now mostly bypassed after the latency fix (§3.4) — kept for the
  reminder/greeting paths and its tests.

### 3.2 New coverage tools (Workstream 3) — all NEW in `Tools/`
- `document_writer.py`: `write_document(app,path,content,format)` [.docx/.md/.txt],
  `edit_existing_file(path,operation,detail)` [find_replace/append/insert_at_line].
- `powerpoint_tool.py`: `create_presentation`, `edit_presentation` (python-pptx).
  **Did NOT touch the existing .pptx file.**
- `file_ops.py`: rename/move/copy/`delete_file_or_folder`(now uses Recycle Bin via
  `send2trash`, requires confirm)/search_files_by_content/zip/unzip/batch_rename.
- `browser_automation.py`: `browser_automate` (Playwright).
- `send_email.py`: SMTP via `.env` (clear "not configured" message if unset).
- `excel_data_entery.py`: added `enter_excel_formula`, `create_excel_chart`
  (uses openpyxl `range_boundaries` — fixed a dead-branch bug found in audit).
- `computer_use.py`: added `click_text` OCR action; **removed `shell=True`**
  launch (injection-safe `os.startfile` + argv-list fallback).
- `multi_task.py`: fixed `execute_multi_task` (was `globals().get()` -> now
  resolves via `tool_registry.get_tool_by_name`).

### 3.3 Router bug fixes (the owner's real complaints)
- **Dangerous power-action false triggers (D-02)**: "how do i block ads", "sleep
  apnea", "clock speed" were LOCKING/SLEEPING the PC via bare substring match.
  Rewrote the system-power block to **intent-anchored regex** + question/explanation
  guard ("what does shutdown mean", "restart a router" no longer fire). Genuine
  "lock the computer"/"shut down"/etc. still work. shutdown/restart/hibernate go
  through a `pending_confirmation` gate (yes/no next turn, 20s expiry).
- **WhatsApp natural phrasing (D-01)**: broadened regex to "send message to X
  saying Y", "text X saying Y", Hinglish "X ko Y bhejo", + **slot-fill**
  (`pending_slot`): "send message to naveen" -> asks "What should I say?" -> next
  utterance becomes the body (fixes the re-ask bug).
- **Spotify (D-01)**: "play a song"/"some music" (entity-less) now resumes/plays
  liked instead of searching literal "a song"; "play stop by spice girls" plays
  (doesn't pause on the "stop" substring); "play my liked songs" -> liked branch
  (fixed ordering bug caught by expanded tests).
- **Local vs web search**: "search this file"/"search X on my computer" ->
  `universal_file_opener` (local), real web searches still -> `search_web`.
- **Word-boundary matching** for open/close app ("close the code editor" -> code;
  "write code for X" does NOT open VS Code).
- **Filler-stripper hardening**: "my"/"the" only stripped as leading tokens;
  removed verb-eating "open my"/"launch my" fillers (fixed "open my notepad").
- **Ambiguity guard**: bare "open"/"close"/"search" alone -> asks "X what?".
- **N-01 tool-registration gap**: added the missing action tools (open_app,
  whatsapp, all spotify_*, volume/brightness, press_key, etc.) to the LLM tool
  list so natural phrasings reaching Gemini can actually execute.

### 3.4 LATENCY fixes (the main recent focus)
- **Turn-state wedge (the "stuck after 2-3 commands" bug)**: the LLM-fallback
  branch never reset `turn_ctx.state` to IDLE -> every later command hit
  "PREEMPTING" for 30s. Fixed to always `_finish_direct_turn`.
- **Indic-script transcripts**: `core/textnorm.py` (NEW) transliterates any
  non-Latin STT output to English (unidecode + phonetic-alias snap + difflib
  lexicon). Wired into `on_user_transcript` (display + routing) and
  `handle_user_transcript` (typed path). So any language spoken -> bubble shows
  English + routes in English.
- **Task overlap**: added a global `_input_lock` (asyncio.Lock) around every tool
  call in `run_tool_helper` so two tools can't drive keyboard/mouse at once;
  multi-step splitter no longer splits message/write payloads (D-10).
- **Idle/hang after a few tasks**: `speak_local_background` reset
  `is_speaking_locally=False` only AFTER `session.say()` — if say() hung,
  commands were dropped forever. Now wrapped in `asyncio.wait_for(..., 12s)` +
  `finally` reset. Lowered stuck-turn backstop 30s -> 12s.
- **Progressive slowdown (resource accumulation)**: 
  - Capped `latency_history` to a rolling 50 (was unbounded + O(n) avg per turn).
  - **Orphaned task fix**: `on_user_transcript` now cancels the previous
    `handle_user_transcript` task and tracks `_active_turn_task` with a
    done-callback (was fire-and-forget, piling up on `_input_lock`).
  - **Non-blocking logging**: the global print->file bridge now uses a
    `QueueHandler` + background `QueueListener` (was synchronous disk I/O on the
    event loop every print, ~12-20/turn).
- **THE BIG ONE — native-passthrough (MJ ideology, spec D-05)**: compared to the
  original fast MJ `agent.py` which has NO router/abort/re-prompt and lets Gemini
  answer natively in ONE round-trip. Tony was: abort Gemini up-front -> route ->
  on miss call `generate_reply` (a SECOND full model round-trip). **Fixed**:
  removed the up-front abort and the `generate_reply` re-prompt. Now on a router
  MISS, Gemini's native turn answers (one round-trip, like MJ). The router still
  aborts Gemini only when IT handles a command (each intent aborts itself).
- **Responsiveness**: `on_user_transcript` no longer blanket-drops all input while
  Tony speaks + 0.8s after; only drops genuine self-echo (similarity >= 0.8),
  so a new command during/after the confirmation is accepted immediately.

### 3.5 Tests (doubled this session: 108 -> 202)
Files in `tests/`: conftest.py (FakeSession + runtime_agent fixture),
test_router.py, test_execute_tool.py, test_tool_registry.py, test_coverage_tools.py,
test_gemini_retry.py, test_startup_self_check.py, test_timing_log.py,
test_turn_lifecycle.py, test_ambiguity.py, test_owner_regressions.py,
test_commit_regressions.py, test_overlap_wedge.py, test_latency_leaks.py,
test_textnorm.py, **test_latency.py** (NEW, measures hot-path latency),
**test_matrix_paraphrases.py** (NEW, ~90 paraphrase+negative cases),
**test_native_passthrough.py** (NEW, proves no 2nd round-trip on miss).
Plus `tests/MANUAL_QA_CHECKLIST.md` for rows needing real hardware.

### 3.6 Deps added to requirements.txt
python-pptx, playwright, pywin32, pytest, pytest-asyncio, send2trash,
unidecode, indic-transliteration. (Installed in the venv.)

### 3.7 Git
One push done mid-session (commit `4037e68` "Fix turn-state wedge, reliability +
coverage upgrades, add tests"). **Everything after `4037e68` is UNPUSHED** — the
latency fixes (§3.4), textnorm, overlap/wedge fixes, Spotify liked fix, and the
doubled test suite are all local only. Next session: review + push.

---

## 4. KNOWN REMAINING WORK (not done — honest backlog)

Ranked by value. These are from the two big spec docs (FINAL_UPGRADE_PROMPT +
TEST_MATRIX) that we only partially executed.

1. **Live latency measurement**: in-process code is proven fast (~1ms router).
   The real 4-6s is the Gemini Realtime STT/TTS network round-trip. Need a real
   run's `logs/tony.log` [PERF] lines / `turn_timings` to confirm where time goes.
   Likely next win = **WP6: pre-rendered local audio acks** (winsound, ~30 short
   clips) instead of network TTS confirmations.
2. **VAD / endpointing tuning**: Tony overrides `min_endpointing_delay=0.05`,
   `max_endpointing_delay=0.20`, custom Silero VAD (`activation_threshold=0.3`,
   `min_silence_duration=0.25`). The fast MJ uses NONE of these (defaults). Could
   align to MJ defaults — but needs live-mic testing (changes behavior).
3. **Underlying WhatsApp/Spotify tools still use timed keyboard automation** with
   fixed sleeps and NO verification oracle (D-12). The ROUTER now routes them
   correctly, but the tools themselves can still be slow/miss on a real PC. Real
   fix = WP8/WP9: API-first (Spotify Web API, WhatsApp deep-link + UIA) + a
   verification oracle (media-session PLAYING check, outgoing-bubble OCR) so they
   never report success unverified.
4. **~80 blocking `time.sleep` in Tools/** inside `async def` (D-11) — freeze the
   event loop. core/ is clean (tested). WP2/WP15: convert to `asyncio.to_thread`.
5. **Full intent-engine rewrite (WP4)**: the router is still a long if/elif chain
   (works, ~1ms, but ~25 of its intents still use bare `in clean_command` substring
   checks — not the collision-bug class, but could be tightened to word-boundary).
6. **STT language config (D-21)**: textnorm is a band-aid. The real fix is setting
   the Gemini Live input transcription language to en-IN so English stops coming
   back as Devanagari in the first place. Needs inspecting the installed
   `livekit-plugins-google` RealtimeModel signature.
7. **Windows IO foundation (WP2 `core/winio.py`)**: known-folder resolution
   (OneDrive-safe), DPI awareness, Unicode-safe type_text, reliable focus — many
   file/app tools hard-code `~/Desktop` etc. (D-14, 18 sites).
8. **Agentic desktop lane (WP14 `do_on_desktop`)**, parity benchmark (T21),
   soak/chaos (T19), environment matrix (T18) — all need live hardware.

---

## 5. KEY FILES MAP

| File | Role |
|---|---|
| `core/runtime_agent.py` | THE runtime: router, turn handling, execute_tool, timing, startup check. Most changes live here. |
| `core/textnorm.py` | NEW. Indic-script -> English transcript normaliser. |
| `core/prompts.py` | Persona + tool manifest. |
| `core/logging_config.py` | NEW. Rotating logger + accuracy log. |
| `tool_registry.py` | NEW. Single source of truth for tools + timeout tiers + name lookup. |
| `tools.py` | Thin facade re-exporting tool_registry. |
| `memory_db.py` | SQLite memory + turn_timings (schema v2). |
| `Tools/tool_result.py` | NEW. ok/fail/is_failure contract. |
| `Tools/{document_writer,powerpoint_tool,file_ops,browser_automation,send_email}.py` | NEW coverage tools. |
| `tony.py` | FROZEN UI — do not modify. |
| `tests/` | 202 tests + MANUAL_QA_CHECKLIST.md. |

---

## 6. QUICK START FOR NEXT SESSION

1. `cd C:\Users\DELL\Desktop\MJ` ; run `pytest tests/ -q` — expect 202 passed.
2. Decide: push the unpushed latency work to GitHub first (recommended).
3. If latency still reported: get a real `logs/tony.log` from a live run, read the
   `[PERF]` lines to see which stage (Speech->Transcript / Router / Tool / TTS)
   dominates, then target that (likely WP6 local audio acks).
4. Preserve the constraints in §0. Verify every fix with a failing-test-first +
   logfile-based evidence (shell stdout is unreliable here for non-ASCII).
