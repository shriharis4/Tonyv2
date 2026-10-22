import sys
import builtins
import logging
import logging.handlers
import os as _os_for_log
from pathlib import Path as _PathForLog

# =========================
# GLOBAL PRINT -> ROTATING LOG FILE BRIDGE
# =========================
# Every print() call across the whole app (runtime_agent.py AND every
# Tools/*.py module, since builtins.print is patched process-wide) is
# mirrored to a rotating log file. This gives persistent, structured logs
# for post-hoc debugging without requiring call-site-by-call-site
# migration of ~140+ existing print() statements, while still printing to
# the console for live debugging.
_LOG_DIR = _PathForLog(__file__).resolve().parents[1] / "logs"
_LOG_DIR.mkdir(exist_ok=True)
_file_log_handler = logging.handlers.RotatingFileHandler(
    _LOG_DIR / "tony.log", maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
)
_file_log_handler.setFormatter(logging.Formatter("%(asctime)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
_file_logger = logging.getLogger("tony.console")
_file_logger.setLevel(logging.INFO)
_file_logger.addHandler(_file_log_handler)
_file_logger.propagate = False

# Safe print wrapper to prevent UnicodeEncodeError on legacy Windows consoles
_original_print = print
def print(*args, **kwargs):
    enc = getattr(sys.stdout, 'encoding', 'utf-8') or 'utf-8'
    new_args = []
    for arg in args:
        if isinstance(arg, str):
            try:
                arg.encode(enc)
                new_args.append(arg)
            except UnicodeEncodeError:
                new_args.append(arg.encode(enc, errors='replace').decode(enc))
        else:
            new_args.append(arg)
    _original_print(*new_args, **kwargs)
    try:
        sep = kwargs.get('sep', ' ')
        _file_logger.info(sep.join(str(a) for a in new_args))
    except Exception:
        pass  # Logging must never break the app's console output.

builtins.print = print

if __name__ == "__main__":
    sys.modules['agent'] = sys.modules['__main__']

# =========================
# ENV + CORE IMPORTS
# =========================
from dotenv import load_dotenv
import asyncio
import os
import numpy as np
import time
import json
import socket
import logging
import difflib
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
import threading

PROJECT_ROOT = Path(__file__).resolve().parents[1]
_ENV_PATH = PROJECT_ROOT / ".env"
load_dotenv(dotenv_path=_ENV_PATH)
if not _ENV_PATH.exists():
    print(f"[ENV ERROR] Missing {_ENV_PATH}. Copy .env.example to .env and fill credentials.")

# Validate required environment variables for listening to work
_required_env_vars = ["LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET"]
_missing_vars = [var for var in _required_env_vars if not os.getenv(var)]
if _missing_vars:
    print(f"\n[CRITICAL ERROR] Missing required environment variables: {', '.join(_missing_vars)}")
    print(f"[CRITICAL ERROR] Tony cannot enter listening mode without these credentials.")
    print(f"[CRITICAL ERROR] Please set them in {_ENV_PATH} or as environment variables.")
    print(f"[CRITICAL ERROR] See .env.example for documentation.\n")
    # Don't exit; allow UI to show error message

TONY_AGENT_NAME = os.getenv("LIVEKIT_AGENT_NAME", "tony")
# Set when the LiveKit AgentSession is actually listening (not a UI-only flag).
agent_listening_flag = threading.Event()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# =========================
# LIVEKIT IMPORTS
# =========================
from livekit import agents, rtc
from livekit.agents import Agent, AgentSession, RoomInputOptions
from livekit.plugins import noise_cancellation
from livekit.plugins import silero

# Gemini realtime (network-safe & import-safe)
# NOTE: `network_available` here really means "RealtimeModel SDK import
# succeeded" (checked once, at import time) — it is NOT a live network
# reachability signal. Use `is_network_reachable()` below for an
# up-to-date runtime check instead of trusting this flag indefinitely.
network_available = False
import_error = None
try:
    from livekit.plugins.google.realtime import RealtimeModel
    network_available = True
except Exception as e1:
    try:
        from livekit.plugins.google.beta.realtime import RealtimeModel
        network_available = True
    except Exception as e2:
        import_error = f"Path 1: {e1} | Path 2: {e2}"
        print(f"[WARN] Failed to import RealtimeModel from both paths: {import_error}")


def is_network_reachable(host: str = "8.8.8.8", port: int = 53, timeout: float = 2.0) -> bool:
    """
    Lightweight, fast runtime connectivity check (TCP connect to a
    well-known DNS endpoint) — re-checked on demand rather than relying on
    a flag captured once at import time. Used by the Gemini retry/backoff
    path to distinguish "SDK unavailable" from "network currently down".
    """
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


# =========================
# PROMPTS
# =========================
from .prompts import (
    AGENT_INSTRUCTION,
    SESSION_INSTRUCTION,
    AGENT_INSTRUCTION_FOR_TOOLS,
)

# =========================
# TOOLS (ALL) — single source of truth: tool_registry.py
# =========================
from tool_registry import (
    manage_window, list_windows,
    search_web,
    send_whatsapp_message, send_whatsapp_message_advanced,
    system_power_action,
    type_user_message_auto, create_essay_in_notepad, write_essay_in_notepad,
    write_in_notepad,
    desktop_control,
    scroll_content,
    fix_code_error,
    universal_file_opener,
    press_key, use_smart_clipboard,
    open_app,
    scan_system_for_viruses,
    control_screen_brightness, control_system_volume, get_time_info, get_weather,
    get_system_info_deep, get_current_volume, get_system_status,
    execute_multi_task,
    generate_ai_image,
    generate_and_type_code, run_file_in_vscode,
    get_top_news,
    play_media,
    set_reminder, view_reminders, cancel_reminder,
    screen_short,
    process_document_query,
    send_media_to_whatsapp,
    create_excel_file, save_excel_changes, delete_all_data, move_left, move_up,
    enter_data_quick, enter_multiple_data_quick, move_down, move_right,
    delete_current_cell, go_to_cell, toggle_text_bold, select_row_or_column,
    sort_excel_data, excel_clipboard_action, calculate_sum,
    enter_excel_formula, create_excel_chart,
    word_to_pdf, image_to_pdf, excel_to_pdf, ppt_to_pdf, convert_image_format, test_converters,
    create_here,
    read_screen_text,
    camera_analysis,
    analyze_screen,
    analyze_local_image, identify_objects_in_image, extract_text_from_image,
    analyze_photo_composition, detect_image_authenticity,
    describe_image_for_visually_impaired, get_image_color_analysis, compare_images,
    open_spotify, spotify_next, spotify_previous, spotify_play_song,
    spotify_play_liked, spotify_pause, spotify_play,
    click_on_screen_text, click_text, find_all_text, verify_ocr_setup,
    schedule_task, view_scheduled_tasks, cancel_scheduled_task,
    web_scraper,
    perform_computer_action,
    # Workstream 3 additions
    write_document, edit_existing_file,
    create_presentation, edit_presentation,
    rename_file_or_folder, move_file_or_folder, copy_file_or_folder,
    delete_file_or_folder, search_files_by_content, zip_paths, unzip_archive,
    batch_rename,
    browser_automate,
    send_email,
    get_tool_timeout,
    get_all_tool_functions,
)
from Tools.tool_result import ok as tool_ok, fail, is_failure
from core.logging_config import get_logger, log_turn_outcome

router_logger = get_logger("router")
tool_logger = get_logger("tool")



# =========================
# GUI CALLBACKS & SIGNAL BRIDGE
# =========================
import re
import functools

_gui_callbacks = {
    'update_status': None,
    'update_command': None,
    'update_response': None,
    'update_connection': None,
    'update_latency': None,
    'update_mic_status': None,
    # Streaming callbacks for word-by-word chat display
    'stream_start': None,
    'stream_chunk': None,
    'stream_end': None,
    # Partial-transcript streaming (replaces current text instead of appending)
    'stream_replace': None,
    # One-shot static bubble (used when loading history)
    'add_static_bubble': None,
}

active_room = None
worker_loop = None

def setup_rpc_proxies():
    import json
    keys = [
        'stream_start', 'stream_chunk', 'stream_end', 'stream_replace',
        'update_response', 'update_command', 'update_status',
        'update_connection', 'update_latency', 'update_mic_status',
        'add_static_bubble'
    ]
    for key in keys:
        if _gui_callbacks.get(key) is None:
            def make_proxy(k):
                def proxy(*args):
                    global active_room, worker_loop
                    if active_room and active_room.isconnected() and worker_loop:
                        try:
                            payload = json.dumps({"callback": k, "args": list(args)})
                            asyncio.run_coroutine_threadsafe(
                                active_room.local_participant.publish_data(payload, topic="tony_gui_rpc"),
                                worker_loop
                            )
                        except Exception as e:
                            pass
                return proxy
            _gui_callbacks[key] = make_proxy(key)

def register_gui_callbacks(update_status=None, update_command=None, update_response=None,
                           update_connection=None, update_latency=None, update_mic_status=None,
                           stream_start=None, stream_chunk=None, stream_end=None,
                           stream_replace=None, add_static_bubble=None):
    _gui_callbacks['update_status'] = update_status
    _gui_callbacks['update_command'] = update_command
    _gui_callbacks['update_response'] = update_response
    _gui_callbacks['update_connection'] = update_connection
    _gui_callbacks['update_latency'] = update_latency
    _gui_callbacks['update_mic_status'] = update_mic_status
    _gui_callbacks['stream_start'] = stream_start
    _gui_callbacks['stream_chunk'] = stream_chunk
    _gui_callbacks['stream_end'] = stream_end
    _gui_callbacks['stream_replace'] = stream_replace
    _gui_callbacks['add_static_bubble'] = add_static_bubble

def update_gui_status(status: str):
    if _gui_callbacks['update_status']:
        _gui_callbacks['update_status'](status)

def update_gui_command(command: str):
    """Legacy: show user command as a static bubble."""
    if _gui_callbacks.get('add_static_bubble'):
        try:
            _gui_callbacks['add_static_bubble']('You', command)
        except Exception:
            pass
    elif _gui_callbacks.get('update_command'):
        _gui_callbacks['update_command'](command)

# -----------------------------------------------------------------------
# PARTIAL TRANSCRIPT — same bubble updates as user speaks, then finalizes
# -----------------------------------------------------------------------
_partial_transcript_open = False

def update_gui_partial_transcript(text: str, is_final: bool):
    """Show partial STT transcript in-place; create one bubble until is_final."""
    global _partial_transcript_open
    if not text or not text.strip():
        return
    has_stream = (
        _gui_callbacks.get('stream_start') and
        _gui_callbacks.get('stream_replace') and
        _gui_callbacks.get('stream_end')
    )
    if not has_stream:
        # Fallback
        if is_final:
            update_gui_command(text)
        return
    if not _partial_transcript_open:
        try:
            _gui_callbacks['stream_start']('You')
        except Exception:
            return
        _partial_transcript_open = True
    try:
        _gui_callbacks['stream_replace'](text)
    except Exception:
        pass
    if is_final:
        try:
            _gui_callbacks['stream_end']()
        except Exception:
            pass
        _partial_transcript_open = False

# -----------------------------------------------------------------------

# -----------------------------------------------------------------------
# STREAMING RESPONSE — word-by-word push to GUI
# -----------------------------------------------------------------------
import threading
import asyncio
_stream_lock = threading.Lock()
_current_stream_task = None

def _cancel_pending_stream():
    """Cancel any in-flight streaming task from previous response."""
    global _current_stream_task
    if _current_stream_task is not None and not _current_stream_task.done():
        _current_stream_task.cancel()
    _current_stream_task = None

def update_gui_response(response: str):
    """Stream the response word-by-word to the GUI chat bubble."""
    if not response or not response.strip():
        return

    _cancel_pending_stream()

    has_streaming = (
        _gui_callbacks.get('stream_start') and
        _gui_callbacks.get('stream_chunk') and
        _gui_callbacks.get('stream_end')
    )

    if not has_streaming:
        # Fallback: old-style single-shot update
        if _gui_callbacks.get('update_response'):
            _gui_callbacks['update_response'](response)
        return

    # Start a new streaming bubble
    try:
        _gui_callbacks['stream_start']('TONY')
    except Exception:
        return

    # Split into small chunks (2-3 words each) for a live-typing feel
    words = response.split()
    CHUNK_SIZE = 3          # words per chunk
    DELAY_S = 0.025        # 25ms between chunks

    chunks = []
    for i in range(0, len(words), CHUNK_SIZE):
        chunk = ' '.join(words[i:i + CHUNK_SIZE])
        # Add trailing space between chunks, except the last
        if i + CHUNK_SIZE < len(words):
            chunk += ' '
        chunks.append(chunk)

    async def _stream_coro():
        for idx, chunk in enumerate(chunks):
            is_last = (idx == len(chunks) - 1)
            try:
                if _gui_callbacks.get('stream_chunk'):
                    _gui_callbacks['stream_chunk'](chunk)
                if is_last and _gui_callbacks.get('stream_end'):
                    _gui_callbacks['stream_end']()
            except Exception as e:
                print(f"[STREAM] chunk send error: {e}")
                break
            if not is_last:
                await asyncio.sleep(DELAY_S)

    global _current_stream_task
    try:
        loop = asyncio.get_running_loop()
        _current_stream_task = loop.create_task(_stream_coro())
    except RuntimeError:
        pass

def update_gui_connection(status_str: str):
    if _gui_callbacks['update_connection']:
        _gui_callbacks['update_connection'](status_str)

def update_gui_latency(last: float, avg: float):
    if _gui_callbacks.get('update_latency'):
        _gui_callbacks['update_latency'](last, avg)

def update_gui_mic_status(status: str):
    if _gui_callbacks.get('update_mic_status'):
        _gui_callbacks['update_mic_status'](status)


# =========================
# TOOL TIMING DECORATOR
# =========================
def make_timing_decorator(func):
    if asyncio.iscoroutinefunction(func):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            global turn_ctx
            my_turn_id = turn_ctx.turn_id
            tool_name = func.__name__
            print(f"[TOOL] {tool_name} started (Turn {my_turn_id})")
            start_time = time.perf_counter()
            try:
                res = await func(*args, **kwargs)
                duration = time.perf_counter() - start_time
                if turn_ctx.turn_id != my_turn_id:
                    print(f"[TOOL] {tool_name} completed but turn changed ({my_turn_id} -> {turn_ctx.turn_id}). Suppressing result.")
                    return "Task cancelled because the user interrupted with a new command. Do not mention this cancellation, just respond to the user's latest command."
                print(f"[TOOL] {tool_name} completed: {duration:.2f}s")
                return res
            except Exception as e:
                duration = time.perf_counter() - start_time
                if turn_ctx.turn_id != my_turn_id:
                    print(f"[TOOL] {tool_name} failed but turn changed. Suppressing.")
                    return "Task cancelled due to interruption."
                print(f"[TOOL] {tool_name} failed after {duration:.2f}s: {e}")
                raise e
        return async_wrapper
    else:
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            global turn_ctx
            my_turn_id = turn_ctx.turn_id
            tool_name = func.__name__
            print(f"[TOOL] {tool_name} started (Turn {my_turn_id})")
            start_time = time.perf_counter()
            try:
                res = func(*args, **kwargs)
                duration = time.perf_counter() - start_time
                if turn_ctx.turn_id != my_turn_id:
                    print(f"[TOOL] {tool_name} completed but turn changed. Suppressing result.")
                    return "Task cancelled because the user interrupted with a new command. Do not mention this cancellation, just respond to the user's latest command."
                print(f"[TOOL] {tool_name} completed: {duration:.2f}s")
                return res
            except Exception as e:
                duration = time.perf_counter() - start_time
                if turn_ctx.turn_id != my_turn_id:
                    print(f"[TOOL] {tool_name} failed but turn changed. Suppressing.")
                    return "Task cancelled due to interruption."
                print(f"[TOOL] {tool_name} failed after {duration:.2f}s: {e}")
                raise e
        return sync_wrapper


# =========================
# WAKE WORD & DIRECT ROUTER
# =========================
# =========================
# WAKE WORD, DIRECT ROUTER & PERFORMANCE TIMERS
# =========================
import win32com.client

class TurnTimer:
    def __init__(self):
        self.t0 = time.perf_counter()  # Microphone detected / session start
        self.t1 = None         # Speech started
        self.t2 = None         # Speech ended
        self.t3 = None         # Transcript received
        self.t4 = None         # Command router started
        self.t5 = None         # LLM request started
        self.t6 = None         # LLM response received
        self.t7 = None         # Tool started
        self.t8 = None         # Tool completed
        self.t9 = None         # Response started
        self.t10 = None        # Response completed
        
        self.command = ""
        self.tool_name = ""
        self.logged = False

    def print_perf(self):
        if self.logged:
            return
        self.logged = True
        print("\n" + "="*50)
        print(" [PERF] PERFORMANCE METRICS FOR THIS TURN:")
        print(f" [PERF] Command: '{self.command}'")
        
        # Calculate timings
        if self.t1 and self.t3:
            speech_end = self.t2 if self.t2 else self.t1
            print(f"[PERF] Speech → Transcript: {self.t3 - speech_end:.2f}s")
        if self.t3 and self.t4:
            print(f"[PERF] Transcript → Router: {self.t4 - self.t3:.2f}s")
        if self.t4 and self.t7:
            print(f"[PERF] Router → Tool: {self.t7 - self.t4:.2f}s")
        if self.t7 and self.t8:
            print(f"[PERF] Tool: {self.t8 - self.t7:.2f}s")
        if self.t9 and self.t10:
            print(f"[PERF] TTS: {self.t10 - self.t9:.2f}s")
            
        start_time = self.t1 or self.t3 or self.t0
        end_time = self.t10 or self.t8 or time.perf_counter()
        total_latency = end_time - start_time
        print(f"[PERF] TOTAL: {total_latency:.2f}s")
        print("="*50 + "\n")
        
        global latency_history
        latency_history.append(total_latency)
        avg_latency = sum(latency_history) / len(latency_history)
        update_gui_latency(total_latency, avg_latency)

        # Persist this turn's timing breakdown to SQLite for offline latency
        # analysis (computing p50/p95 over many turns). Best-effort and
        # non-blocking: failures here must never affect the turn.
        try:
            _persist_turn_timing(self, total_latency)
        except Exception:
            pass

current_timer = None

# Shared memory DB handle for timing persistence (lazy, best-effort).
_timing_db = None


def _persist_turn_timing(timer, total_latency: float) -> None:
    """Write a TurnTimer's latency breakdown to the SQLite turn_timings
    table. Lazily opens a single shared MemoryDatabase. Any failure is
    swallowed by the caller so it never affects the live turn."""
    global _timing_db
    if _timing_db is None:
        from memory_db import MemoryDatabase
        _timing_db = MemoryDatabase()

    def _seg(a, b):
        return (b - a) if (a and b) else None

    route = "direct" if (timer.t7 and timer.t8) else "llm"
    _timing_db.log_turn_timing(
        command=timer.command or "",
        route=route,
        total_latency=round(total_latency, 3),
        speech_to_transcript=_seg(timer.t2 or timer.t1, timer.t3),
        transcript_to_router=_seg(timer.t3, timer.t4),
        router_to_tool=_seg(timer.t4, timer.t7),
        tool_duration=_seg(timer.t7, timer.t8),
        tts_duration=_seg(timer.t9, timer.t10),
    )


def get_or_create_timer():
    global current_timer
    if current_timer is None:
        current_timer = TurnTimer()
    return current_timer

def reset_timer():
    global current_timer
    current_timer = TurnTimer()
    return current_timer

class TurnContext:
    def __init__(self):
        self.turn_id = 0
        self.state = "IDLE"  # IDLE, RECEIVED, ROUTING, DIRECT_EXECUTION, LLM_EXECUTION
        self.last_handled_transcript = ""
        self.last_handled_at = 0.0
        self.last_processed_command = ""
        self.last_processed_at = 0.0
        self.last_spoken_text = ""
        self.is_active = True
        # Pending destructive-action confirmation gate. When a destructive
        # action (shutdown/restart/hibernate, file delete) is requested,
        # the router sets this instead of executing immediately, and only
        # fires on an explicit affirmative reply within the time window.
        self.pending_confirmation = None  # {"action": str, "handler": callable, "requested_at": float}
        
    def next_turn(self):
        self.turn_id += 1
        self.state = "RECEIVED"
        return self.turn_id
        
    def is_current_turn(self, turn_id):
        return self.turn_id == turn_id

turn_ctx = TurnContext()
active_timeout_task = None
is_speaking_locally = False
last_local_speech_end = 0.0

def _normalize_command(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text.strip().lower())

async def execute_tool(func, *args, **kwargs):
    """
    Execute a tool callable with a timeout tiered by tool category
    (in_process ~2s, app_launch ~8s, network ~15s — see
    tool_registry.get_tool_timeout()), with crash isolation so a single
    tool exception or hang can never take down the turn or the
    AgentSession.

    Returns the tool's own result string on success. On timeout or
    exception, returns a structured failure string (see Tools/tool_result.py)
    instead of raising — callers in the router/LLM-tool-calling path should
    never need a bare try/except around this call.
    """
    # Unpack FunctionTool wrapper if present
    target_func = func
    if hasattr(func, "_func"):
        target_func = func._func
    elif hasattr(func, "__wrapped__"):
        target_func = func.__wrapped__

    tool_name = getattr(target_func, "__name__", "unknown_tool")
    timeout = get_tool_timeout(tool_name)

    try:
        if asyncio.iscoroutinefunction(target_func):
            return await asyncio.wait_for(target_func(*args, **kwargs), timeout=timeout)
        else:
            return await asyncio.wait_for(
                asyncio.get_running_loop().run_in_executor(
                    None, lambda: target_func(*args, **kwargs)
                ),
                timeout=timeout,
            )
    except asyncio.TimeoutError:
        router_logger.warning(f"[TOOL] {tool_name} timed out after {timeout:.0f}s")
        return fail(f"'{tool_name}' timed out after {timeout:.0f} seconds.", detail="timeout")
    except Exception as e:
        router_logger.error(f"[TOOL] {tool_name} raised an exception: {e}", exc_info=True)
        return fail(f"'{tool_name}' failed to execute.", detail=str(e))

def _abort_model_turn(session: AgentSession) -> None:
    """Stop Gemini from also acting on a turn that the direct router already handled."""
    try:
        session.interrupt(force=True)
    except Exception:
        pass
    try:
        session.clear_user_turn()
    except Exception:
        pass


def _finish_direct_turn(session: AgentSession) -> None:
    global turn_ctx
    # session already aborted before routing started. No redundant call.
    turn_ctx.is_active = True  # Keep assistant active so follow-up commands are never dropped
    turn_ctx.state = "IDLE"
    
    
    update_gui_status("Listening...")
    print("[TURN] complete — idle listening (active)")


def _is_repeated_command(clean_text: str, now: float) -> bool:
    global turn_ctx
    current_key = _normalize_command(clean_text)
    if not current_key:
        return True
    if current_key == turn_ctx.last_processed_command and (now - turn_ctx.last_processed_at) < 4.0:
        print("[ROUTER] ignored — repeated command within cooldown")
        return True
    turn_ctx.last_processed_command = current_key
    turn_ctx.last_processed_at = now
    return False


async def speak_local(session: AgentSession, text: str):
    global is_speaking_locally, turn_ctx
    is_speaking_locally = True
    turn_ctx.last_spoken_text = (text or "").strip().lower()
    update_gui_status("Speaking...")
    update_gui_response(text)
    
    # Record T9
    timer = get_or_create_timer()
    timer.t9 = time.perf_counter()
    print(f"[T9] response started: '{text}'")
    
    # Start cloud speaking in the background without blocking the router turn!
    asyncio.create_task(speak_local_background(session, text))

async def speak_local_background(session: AgentSession, text: str):
    global is_speaking_locally
    print("[TTS] response started using Google API / LiveKit")
    print("[AUDIO OUT] audio playback started")
    
    try:
        await session.say(text)
    except Exception as e:
        print(f"⚠️ Cloud speech failed: {e}")
                
    is_speaking_locally = False
    global last_local_speech_end
    last_local_speech_end = time.perf_counter()
    print("[TTS] response finished")
    print("[AUDIO OUT] audio playback finished")
    timer = get_or_create_timer()
    timer.t10 = time.perf_counter()
    print("[T10] response completed")
    timer.print_perf()
    update_gui_status("Listening...")

# Context for desktop actions
active_session = None
background_loop = None
latency_history = []
desktop_context = {
    "last_opened_app": None,
    "last_referenced_file": None,
}

def send_text_command(command: str):
    global background_loop, active_session, turn_ctx
    turn_ctx.is_active = True
    # Clear echo-suppression state so typed commands are never treated as echoes
    turn_ctx.last_spoken_text = ""
    turn_ctx.last_handled_transcript = ""
    if background_loop and active_session:
        asyncio.run_coroutine_threadsafe(
            handle_user_transcript(active_session, command),
            background_loop
        )

async def wait_for_process(process_name: str, timeout: float = 3.0) -> bool:
    import psutil
    start_time = time.perf_counter()
    while time.perf_counter() - start_time < timeout:
        for proc in psutil.process_iter(['name']):
            try:
                if process_name.lower() in proc.info['name'].lower():
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        await asyncio.sleep(0.2)
    return False

async def route_command_directly(session: AgentSession, command: str) -> bool:
    global turn_ctx
    clean_command = command.strip().lower()
    clean_command = re.sub(r'^(hey\s+)?tony\b\s*', '', clean_command).strip()
    clean_command = re.sub(r'^[,\.\?!\s]+|[,\.\?!\s]+$', '', clean_command).strip()
    
    if not clean_command:
        return False

    # --- DESTRUCTIVE ACTION CONFIRMATION GATE ---
    # If a destructive action (shutdown/restart/hibernate) is awaiting
    # confirmation, this turn's utterance is checked against it FIRST,
    # before any other routing. An affirmative reply executes the pending
    # action; anything else (including silence timeout via normal turn
    # flow) cancels it. This guarantees no destructive action ever
    # executes on a single ambiguous utterance. Pending confirmations
    # expire after 20s so a stale "yes" long after the fact can't trigger
    # an old shutdown request.
    if turn_ctx.pending_confirmation:
        pending = turn_ctx.pending_confirmation
        turn_ctx.pending_confirmation = None
        expired = (time.perf_counter() - pending.get("requested_at", 0)) > 20.0
        affirmative = re.search(r'\b(yes|yeah|yep|confirm|do it|go ahead|haan|sure)\b', clean_command)
        negative = re.search(r'\b(no|nope|cancel|don\'?t|stop|nahi)\b', clean_command)
        if affirmative and not negative and not expired:
            print(f"[ROUTER] Destructive action confirmed: {pending['action']}")
            _abort_model_turn(session)
            await pending["handler"]()
            return True
        else:
            reason = "expired" if expired else "no explicit confirmation"
            print(f"[ROUTER] Destructive action cancelled ({reason}): {pending['action']}")
            _abort_model_turn(session)
            await speak_local(session, f"Okay, cancelled. I will not {pending['action']}.")
            return True

    print(f"[ROUTER] Checking direct command: '{clean_command}'")
    timer = get_or_create_timer()
    
    async def run_tool_helper(func, *args, **kwargs):
        timer.t7 = time.perf_counter()
        tool_name = getattr(func, "__name__", "unknown_tool")
        print(f"[T7] tool started: {tool_name}")
        res = await execute_tool(func, *args, **kwargs)
        timer.t8 = time.perf_counter()
        print(f"[T8] tool completed: {tool_name}")
        log_turn_outcome(clean_command, "direct_router", tool_name, not is_failure(res) if isinstance(res, str) else True,
                         detail=res if isinstance(res, str) else "")
        return res

    # Strip conversational filler prefixes recursively.
    # HARDENED (spec Workstream 2 item 5): the bare generic words "my" and
    # "the" are split out into a prefix-only list. Stripping them from the
    # END of a command (as the old greedy stripper did) could corrupt the
    # real target — e.g. a command/target that legitimately ends in "the"
    # or "my". They're only removed as leading filler now, never trailing,
    # and never when they are the entire remaining command.
    fillers = [
        "could you please", "would you please", "can you please",
        "could you", "would you", "can you", "please", "hey tony", "tony",
        "for me", "for us", "me", "now", "immediately", "quickly", "fast",
    ]
    prefix_only_fillers = ["my", "the"]
    changed = True
    while changed:
        changed = False
        for f in fillers:
            if clean_command.startswith(f + " "):
                clean_command = clean_command[len(f) + 1:].strip()
                changed = True
                break
            elif clean_command.endswith(" " + f):
                clean_command = clean_command[:-len(f) - 1].strip()
                changed = True
                break
            elif clean_command == f:
                clean_command = ""
                changed = True
                break
        if changed:
            continue
        # Prefix-only generic words: strip ONLY as a leading token, and only
        # if there is still a real target word after them.
        for f in prefix_only_fillers:
            if clean_command.startswith(f + " ") and len(clean_command) > len(f) + 1:
                clean_command = clean_command[len(f) + 1:].strip()
                changed = True
                break

    # --- AMBIGUITY GUARD (spec Workstream 2 item 4) ---
    # If, after filler stripping, the command is just a bare action verb
    # with no target (e.g. "open", "close", "play", "search"), don't guess
    # a target — ask a short clarifying question via speak_local instead of
    # firing a tool against nothing. "play"/"pause"/"next" alone are handled
    # by the Spotify block (valid as media transport controls), so they're
    # excluded here.
    _bare_ambiguous_verbs = {
        "open", "close", "launch", "start", "exit", "run", "set",
        "search", "google", "message", "whatsapp", "create", "find",
    }
    if clean_command in _bare_ambiguous_verbs:
        print(f"[ROUTER] Ambiguous bare verb '{clean_command}' - asking for clarification")
        _abort_model_turn(session)
        await speak_local(session, f"{clean_command.capitalize()} what?")
        log_turn_outcome(clean_command, "ambiguity_clarification", "none", True, detail="asked for target")
        return True

    # 1. CHECK FOR MULTI-STEP COMMANDS
    if any(sep in clean_command for sep in [" then ", " and ", ","]):
        sub_cmds = []
        parts = re.split(r'\b(?:and|then)\b|,', clean_command)
        verbs = ["open", "launch", "start", "close", "exit", "set", "increase", "decrease", "take", "capture", "search", "play", "type", "press", "create", "find", "read", "summarize", "message"]
        for p in parts:
            p = p.strip()
            if not p:
                continue
            if any(p.startswith(v) for v in verbs) or len(sub_cmds) == 0:
                sub_cmds.append(p)
            else:
                if sub_cmds:
                    sub_cmds[-1] += " " + p
                    
        if len(sub_cmds) > 1:
            print(f"[ROUTER] Detected multi-step command. Split into: {sub_cmds}")
            _abort_model_turn(session)
            
            # Heuristic: Check if steps are strictly independent actions
            independent_verbs = ["open", "launch", "start", "close", "exit", "search", "play", "set", "increase", "decrease"]
            is_independent = all(any(cmd.startswith(v) for v in independent_verbs) for cmd in sub_cmds)
            
            if is_independent:
                print("[ROUTER] Steps are independent, running concurrently.")
                tasks = [route_command_directly(session, step) for step in sub_cmds]
                results = await asyncio.gather(*tasks)
                if not all(results):
                    print("[ROUTER] Some concurrent steps failed to route directly.")
                    return False
            else:
                print("[ROUTER] Steps have dependencies, running sequentially.")
                for i, step in enumerate(sub_cmds):
                    print(f"[ROUTER] Executing step {i+1}: '{step}'")
                    handled = await route_command_directly(session, step)
                    if handled:
                        if "open" in step or "launch" in step:
                            # Extract target and use wait_for_process readiness check instead of guessed sleep
                            m = re.search(r'(?:open|launch|start)\s+(.+)', step)
                            if m:
                                target = m.group(1).strip()
                                proc_map = {"chrome": "chrome", "notepad": "notepad", "calculator": "calculator", "excel": "excel", "code": "code"}
                                proc_name = proc_map.get(target, target)
                                print(f"[ROUTER] Waiting for process '{proc_name}' to be ready...")
                                ready = await wait_for_process(proc_name, timeout=3.0)
                                if not ready:
                                    print(f"[ROUTER] wait_for_process timed out for '{proc_name}', proceeding.")
                            else:
                                pass # Wait removed for latency. Process check was sufficient.
                    else:
                        print(f"[ROUTER] Step {i+1} failed to route directly. Falling back to Gemini.")
                        return False

            await speak_local(session, "Multi task execution complete.")
            return True

    try:
        # Greetings / Wake word response
        if clean_command in ["hello", "hi", "hey", "hello tony", "hey tony", "tony", "yo"]:
            print(f"[ROUTER] Direct command matched: greeting")
            print(f"[ROUTER] intent: greeting")
            _abort_model_turn(session)
            await speak_local(session, "Hello Boss.")
            return True

        # Time (English & Hindi / Hinglish)
        if any(x in clean_command for x in ["what time", "current time", "what's the time", "tell me the time", "time", "टाइम", "समय", "samay", "kitne baje", "baje", "बजे"]):
            now_str = datetime.now().strftime("%I:%M %p")
            print(f"[ROUTER] Direct command matched: time -> {now_str}")
            _abort_model_turn(session)
            if any(x in clean_command for x in ["टाइम", "समय", "samay", "बजे", "baje"]):
                await speak_local(session, f"अभी {now_str} हो रहा है।")
            else:
                await speak_local(session, f"It's {now_str}.")
            return True

        # Date (English & Hindi / Hinglish)
        if any(x in clean_command for x in ["what date", "today's date", "current date", "what is the date", "date", "तारीख", "tarikh", "tareekh", "din", "दिन", "aaj kya hai"]):
            today_str = datetime.now().strftime("%A, %B %d, %Y")
            print(f"[ROUTER] Direct command matched: date -> {today_str}")
            _abort_model_turn(session)
            if any(x in clean_command for x in ["तारीख", "tarikh", "दिन", "din"]):
                await speak_local(session, f"आज की तारीख {datetime.now().strftime('%d %B %Y')} है।")
            else:
                await speak_local(session, f"Today is {today_str}.")
            return True

        # Copy & Paste
        if clean_command in ["copy", "copy this", "copy text", "copy that"]:
            print("[ROUTER] Direct command matched: press_key(ctrl+c)")
            _abort_model_turn(session)
            await run_tool_helper(press_key, "ctrl+c")
            await speak_local(session, "Copied.")
            return True

        if clean_command in ["paste", "paste this", "paste text", "paste that"]:
            print("[ROUTER] Direct command matched: press_key(ctrl+v)")
            _abort_model_turn(session)
            await run_tool_helper(press_key, "ctrl+v")
            await speak_local(session, "Pasted.")
            return True

        # Screenshot
        if any(x in clean_command for x in ["take a screenshot", "screenshot", "capture my screen", "capture screen", "take a picture of my screen"]):
            print("[ROUTER] Direct command matched: screen_short()")
            _abort_model_turn(session)
            await run_tool_helper(screen_short)
            await speak_local(session, "Screenshot taken.")
            return True

        # Folder shortcuts
        if any(x in clean_command for x in ["open", "show", "display"]) and "downloads" in clean_command:
            _abort_model_turn(session)
            dl_path = os.path.join(os.path.expanduser("~"), "Downloads")
            await asyncio.get_running_loop().run_in_executor(None, os.startfile, dl_path)
            await speak_local(session, "Opening Downloads.")
            return True
            
        if any(x in clean_command for x in ["open", "show", "display"]) and "documents" in clean_command:
            _abort_model_turn(session)
            doc_path = os.path.join(os.path.expanduser("~"), "Documents")
            await asyncio.get_running_loop().run_in_executor(None, os.startfile, doc_path)
            await speak_local(session, "Opening Documents.")
            return True
            
        if any(x in clean_command for x in ["open", "show", "display"]) and "desktop" in clean_command:
            _abort_model_turn(session)
            dt_path = os.path.join(os.path.expanduser("~"), "Desktop")
            await asyncio.get_running_loop().run_in_executor(None, os.startfile, dt_path)
            await speak_local(session, "Opening Desktop.")
            return True

        # Window Actions: Minimize / Maximize / Restore
        if "minimize" in clean_command:
            print(f"[ROUTER] Direct command matched: manage_window(minimize, active)")
            _abort_model_turn(session)
            await run_tool_helper(manage_window, "minimize", "active")
            await speak_local(session, "Minimizing window.")
            return True

        if "maximize" in clean_command:
            print(f"[ROUTER] Direct command matched: manage_window(maximize, active)")
            _abort_model_turn(session)
            await run_tool_helper(manage_window, "maximize", "active")
            await speak_local(session, "Maximizing window.")
            return True

        if "restore" in clean_command:
            print(f"[ROUTER] Direct command matched: manage_window(restore, active)")
            _abort_model_turn(session)
            await run_tool_helper(manage_window, "restore", "active")
            await speak_local(session, "Restoring window.")
            return True

        # Close Applications/Active window
        # Word-boundary matching to avoid "close"/"exit" substring collisions
        # (e.g. bare substring checks would also match "exit" inside unrelated
        # words). Target detection also now requires a true word boundary so
        # "code" only matches "code"/"vs code"/"vscode" as whole words, not
        # as a substring of some other target phrase.
        if re.search(r'\b(close|exit|terminate|quit|बंद|band|क्लोज)\b', clean_command):
            close_target = None
            if re.search(r'\b(chrome|browser|क्रोम)\b', clean_command):
                close_target = "chrome"
            elif re.search(r'\bwhatsapp\b', clean_command):
                close_target = "whatsapp"
            elif re.search(r'\bspotify\b', clean_command):
                close_target = "spotify"
            elif re.search(r'\b(vs\s*code|vscode|code)\b', clean_command):
                close_target = "code"
            elif re.search(r'\bnotepad\b', clean_command):
                close_target = "notepad"
            elif re.search(r'\b(calculator|calc)\b', clean_command):
                close_target = "calculator"
            elif re.search(r'\bexcel\b', clean_command):
                close_target = "excel"
            elif re.search(r'\bword\b', clean_command):
                close_target = "word"
            elif re.search(r'\bexplorer\b', clean_command):
                close_target = "explorer"
            elif re.search(r'\btask\s*manager\b', clean_command):
                close_target = "task manager"
            elif re.search(r'\bpaint\b', clean_command):
                close_target = "paint"
            else:
                close_target = "active"
                
            if close_target == "active" and desktop_context.get("last_opened_app"):
                close_target = desktop_context["last_opened_app"]
                
            if close_target:
                print(f"[ROUTER] Direct command matched: manage_window(close, {close_target})")
                _abort_model_turn(session)
                await run_tool_helper(manage_window, "close", close_target)
                if any(x in clean_command for x in ["बंद", "band", "क्लोज"]):
                    await speak_local(session, f"{close_target} बंद कर दिया गया है।")
                else:
                    await speak_local(session, f"Closing {close_target}.")
                return True

        # Open Applications (English, Hindi, Hinglish, Reverse syntax)
        # Word-boundary matching throughout: previously a bare `"code" in
        # clean_command` substring check here would also fire for phrases
        # like "decode this" or "barcode scanner" that happen to contain
        # "code" as a substring. Negative lookahead excludes "write code" /
        # "generate code" phrasing, which means "produce code", not "launch
        # the VS Code app" — that should fall through to Gemini / code tools.
        if re.search(r'\b(open|launch|run|start|show|display|khol|kholo|chalao|karo|ओपन|खोल)\b', clean_command):
            open_target = None
            if re.search(r'\b(chrome|browser)\b', clean_command):
                open_target = "chrome"
            elif re.search(r'\b(recycle|trash|रिसाइकल)\b', clean_command):
                open_target = "recycle bin"
            elif re.search(r'\bwhatsapp\b', clean_command):
                open_target = "whatsapp"
            elif re.search(r'\bspotify\b', clean_command):
                open_target = "spotify"
            elif re.search(r'\b(vs\s*code|vscode)\b', clean_command) or (
                re.search(r'\bcode\b', clean_command) and not re.search(r'\b(write|generate|fix|debug)\s+(\w+\s+)?code\b', clean_command)
            ):
                open_target = "vscode"
            elif re.search(r'\bnotepad\b', clean_command):
                open_target = "notepad"
            elif re.search(r'\b(calculator|calc)\b', clean_command):
                open_target = "calculator"
            elif re.search(r'\bexcel\b', clean_command):
                open_target = "excel"
            elif re.search(r'\bword\b', clean_command):
                open_target = "word"
            elif re.search(r'\b(file\s+explorer|explorer)\b', clean_command):
                open_target = "explorer"
            elif re.search(r'\b(task\s*manager|taskmgr)\b', clean_command):
                open_target = "task manager"
            elif re.search(r'\b(paint|mspaint)\b', clean_command):
                open_target = "paint"
            elif re.search(r'\bsettings\b', clean_command):
                open_target = "settings"
                
            if open_target:
                print(f"[ROUTER] Direct command matched: open_app({open_target})")
                _abort_model_turn(session)
                
                if open_target == "recycle bin":
                    try:
                        await asyncio.get_running_loop().run_in_executor(None, os.startfile, "shell:RecycleBinFolder")
                    except Exception:
                        pass
                    desktop_context["last_opened_app"] = "recycle bin"
                    if "रिसाइकल" in clean_command:
                        await speak_local(session, "रिसाइकल बिन खोल दिया गया है।")
                    else:
                        await speak_local(session, "Opening Recycle Bin.")
                elif open_target == "spotify":
                    await run_tool_helper(open_spotify)
                    desktop_context["last_opened_app"] = "spotify"
                    await speak_local(session, "Opening Spotify.")
                else:
                    await run_tool_helper(open_app, open_target)
                    desktop_context["last_opened_app"] = open_target
                    await speak_local(session, f"Opening {open_target.capitalize()}.")
                return True

        # Volume Controls
        if any(x in clean_command for x in ["volume", "sound", "louder", "quieter", "mute", "unmute"]):
            _abort_model_turn(session)
            if "mute" in clean_command and "unmute" not in clean_command:
                await run_tool_helper(control_system_volume, "mute", 0)
                await speak_local(session, "Volume muted.")
                return True
            elif "unmute" in clean_command:
                await run_tool_helper(control_system_volume, "unmute", 50)
                await speak_local(session, "Volume unmuted.")
                return True
            elif any(x in clean_command for x in ["up", "increase", "louder", "raise"]):
                vol_info = await execute_tool(get_current_volume)
                m = re.search(r'(\d+)%', vol_info)
                curr_vol = int(m.group(1)) if m else 50
                new_vol = min(curr_vol + 10, 100)
                await run_tool_helper(control_system_volume, "set", new_vol)
                await speak_local(session, "Volume increased.")
                return True
            elif any(x in clean_command for x in ["down", "decrease", "quieter", "reduce", "lower"]):
                vol_info = await execute_tool(get_current_volume)
                m = re.search(r'(\d+)%', vol_info)
                curr_vol = int(m.group(1)) if m else 50
                new_vol = max(curr_vol - 10, 0)
                await run_tool_helper(control_system_volume, "set", new_vol)
                await speak_local(session, "Volume decreased.")
                return True
            else:
                m = re.search(r'(?:set\s+)?(?:volume|sound)\s+(?:to\s+)?(\d+)', clean_command)
                if m:
                    vol_level = int(m.group(1))
                    await run_tool_helper(control_system_volume, "set", vol_level)
                    await speak_local(session, f"Volume set to {vol_level} percent.")
                    return True

        # Brightness Controls
        if "brightness" in clean_command or "brighter" in clean_command or "dimmer" in clean_command:
            _abort_model_turn(session)
            import screen_brightness_control as sbc
            try:
                curr_bright = await asyncio.get_running_loop().run_in_executor(
                    None, lambda: sbc.get_brightness()[0]
                )
            except Exception:
                curr_bright = 50
                
            if "up" in clean_command or "increase" in clean_command or "brighter" in clean_command:
                new_bright = min(curr_bright + 10, 100)
                await run_tool_helper(control_screen_brightness, new_bright)
                await speak_local(session, "Brightness increased.")
                return True
            elif "down" in clean_command or "decrease" in clean_command or "dimmer" in clean_command or "reduce" in clean_command:
                new_bright = max(curr_bright - 10, 0)
                await run_tool_helper(control_screen_brightness, new_bright)
                await speak_local(session, "Brightness decreased.")
                return True
            else:
                m = re.search(r'(?:set\s+)?brightness\s+(?:to\s+)?(\d+)', clean_command)
                if m:
                    bright_level = int(m.group(1))
                    await run_tool_helper(control_screen_brightness, bright_level)
                    await speak_local(session, f"Brightness set to {bright_level} percent.")
                    return True

        # Scroll
        if "scroll" in clean_command:
            direction = "down" if "down" in clean_command else "up"
            m = re.search(r'(\d+)\s+times', clean_command)
            times = int(m.group(1)) if m else 5
            print(f"[ROUTER] Direct command matched: scroll_content({direction}, {times})")
            _abort_model_turn(session)
            await run_tool_helper(scroll_content, direction, times)
            await speak_local(session, f"Scrolled {direction}.")
            return True

        # Keyboard press commands
        if "press" in clean_command or "hit" in clean_command:
            key = None
            if "enter" in clean_command:
                key = "enter"
            elif "escape" in clean_command or "esc" in clean_command:
                key = "escape"
            elif "tab" in clean_command:
                key = "tab"
            elif "space" in clean_command:
                key = "space"
            elif "backspace" in clean_command:
                key = "backspace"
            elif "delete" in clean_command:
                key = "delete"
                
            if key:
                print(f"[ROUTER] Direct command matched: press_key({key})")
                _abort_model_turn(session)
                await run_tool_helper(press_key, key)
                await speak_local(session, f"Pressed {key}.")
                return True

        # Folder Creation
        folder_match = re.search(r'create\s+(?:a\s+)?folder\s+(?:called|named)\s+(.+)', clean_command)
        if folder_match:
            folder_name = folder_match.group(1).strip()
            print(f"[ROUTER] Direct command matched: create_here({folder_name})")
            _abort_model_turn(session)
            await run_tool_helper(create_here, folder_name, "folder")
            await speak_local(session, f"Folder {folder_name} created.")
            return True

        # WhatsApp Messaging
        wa_match = re.search(r'(?:message|whatsapp)\s+(\w+)\s+(?:saying|that)\s+(.+)', clean_command)
        if wa_match:
            name = wa_match.group(1)
            msg = wa_match.group(2)
            print(f"[ROUTER] Direct command matched: send_whatsapp_message({name}, {msg})")
            _abort_model_turn(session)
            await run_tool_helper(send_whatsapp_message, name, msg)
            await speak_local(session, f"Message sent to {name}.")
            return True

        # YouTube Media Searches
        if "youtube" in clean_command:
            query_match = re.search(r'(?:search|play)\s+youtube\s+for\s+(.+)', clean_command)
            if not query_match:
                query_match = re.search(r'play\s+(.+?)\s+on\s+youtube', clean_command)
            if query_match:
                query = query_match.group(1).strip()
                print(f"[ROUTER] Direct command matched: play_media({query})")
                _abort_model_turn(session)
                await run_tool_helper(play_media, query)
                await speak_local(session, f"Playing {query} on YouTube.")
                return True

        # Spotify Playbacks
        if "spotify" in clean_command or "music" in clean_command or "song" in clean_command or clean_command in ["play", "pause", "next", "previous", "skip", "go back"]:
            _abort_model_turn(session)
            if "pause" in clean_command or "stop" in clean_command:
                await run_tool_helper(spotify_pause)
                await speak_local(session, "Music paused.")
                return True
            elif "play" in clean_command and "on spotify" not in clean_command:
                await run_tool_helper(spotify_play)
                await speak_local(session, "Resuming Spotify.")
                return True
            elif "next" in clean_command or "skip" in clean_command:
                await run_tool_helper(spotify_next)
                await speak_local(session, "Skipping song.")
                return True
            elif "previous" in clean_command or "go back" in clean_command:
                await run_tool_helper(spotify_previous)
                await speak_local(session, "Previous song.")
                return True
            else:
                m = re.search(r'play\s+(.+?)\s+on\s+spotify', clean_command)
                if m:
                    song = m.group(1).strip()
                    await run_tool_helper(spotify_play_song, song)
                    await speak_local(session, f"Playing {song} on Spotify.")
                    return True

        # Excel Data Entry
        excel_entry_match = re.search(r'(?:enter|write)\s+(.+?)\s+into\s+excel', clean_command)
        if excel_entry_match:
            data = excel_entry_match.group(1).strip()
            print(f"[ROUTER] Direct command matched: enter_data_quick({data})")
            _abort_model_turn(session)
            await run_tool_helper(enter_data_quick, data)
            await speak_local(session, f"Entered {data} in Excel.")
            return True

        if any(x in clean_command for x in ["calculate total", "calculate the total", "calculate sum"]):
            print("[ROUTER] Direct command matched: calculate_sum()")
            _abort_model_turn(session)
            await run_tool_helper(calculate_sum)
            await speak_local(session, "Sum calculated in Excel.")
            return True

        # PDF document interactions
        pdf_match = re.search(r'(?:open|find)\s+(?:the\s+)?(.+?)\s+pdf', clean_command)
        if pdf_match:
            query = pdf_match.group(1).strip()
            _abort_model_turn(session)
            loop = asyncio.get_running_loop()
            path = await loop.run_in_executor(None, find_and_open_file, query, "pdf")
            if path:
                desktop_context["last_referenced_file"] = path
                await speak_local(session, f"Opening PDF: {os.path.basename(path)}.")
            else:
                await speak_local(session, f"Could not find PDF matching '{query}'.")
            return True

        # Read specific PDF page index
        page_match = re.search(r'read\s+(?:the\s+)?(?:second|(\d+))(?:\s+page)?', clean_command)
        if page_match:
            page_num_str = page_match.group(1)
            page_num = int(page_num_str) - 1 if page_num_str else 1
            _abort_model_turn(session)
            pdf_path = desktop_context.get("last_referenced_file")
            if pdf_path and pdf_path.lower().endswith(".pdf"):
                loop = asyncio.get_running_loop()
                text = await loop.run_in_executor(None, extract_pdf_page, pdf_path, page_num)
                print(f"[ROUTER] Extracted text from PDF page: '{text[:100]}...'")
                await speak_local(session, f"Reading from PDF. {text[:300]}")
            else:
                await speak_local(session, "No active PDF document context found. Please open a PDF first.")
            return True

        # === NEW DIRECT ROUTES (Build 6) — close coverage gaps ===

        # Web search — "search for X", "google X", "look up X"
        search_match = re.search(r'(?:search\s+(?:the\s+web\s+)?(?:for\s+)?|google\s+|look\s+up\s+)(.+)', clean_command)
        if search_match:
            query = search_match.group(1).strip()
            if query:
                print(f"[ROUTER] Direct command matched: search_web({query})")
                _abort_model_turn(session)
                result = await run_tool_helper(search_web, query)
                response = result if isinstance(result, str) else f"Here are the results for '{query}'."
                await speak_local(session, response[:300])
                return True

        # Weather — "what's the weather", "weather in X"
        weather_match = re.search(r'(?:what\'?s\s+the\s+weather|how\'?s\s+the\s+weather|weather|temperature)\s*(?:in|at|for)?\s*(.*)', clean_command)
        if weather_match and ("weather" in clean_command or "temperature" in clean_command):
            city = weather_match.group(1).strip() or "auto"
            print(f"[ROUTER] Direct command matched: get_weather({city})")
            _abort_model_turn(session)
            result = await run_tool_helper(get_weather, city)
            response = result if isinstance(result, str) else f"Weather information retrieved."
            await speak_local(session, response[:300])
            return True

        # News — "latest news", "top news", "tell me the news"
        if any(x in clean_command for x in ["news", "headlines"]):
            print("[ROUTER] Direct command matched: get_top_news()")
            _abort_model_turn(session)
            result = await run_tool_helper(get_top_news)
            response = result if isinstance(result, str) else "Here are the top news stories."
            await speak_local(session, response[:300])
            return True

        # System power — shutdown, restart, lock, sleep, hibernate
        if any(x in clean_command for x in ["shut down", "shutdown", "restart", "reboot", "lock", "sleep", "hibernate"]):
            action = "shutdown"
            if "restart" in clean_command or "reboot" in clean_command:
                action = "restart"
            elif "lock" in clean_command:
                action = "lock"
            elif "sleep" in clean_command:
                action = "sleep"
            elif "hibernate" in clean_command:
                action = "hibernate"

            # Destructive/disruptive actions (shutdown/restart/hibernate) require
            # explicit confirmation before executing — never fire on a single
            # ambiguous utterance. Lock/sleep are reversible and execute immediately.
            if action in ("shutdown", "restart", "hibernate"):
                print(f"[ROUTER] system_power_action({action}) requires confirmation - asking user")
                _abort_model_turn(session)

                async def _confirmed_power_action(a=action):
                    await run_tool_helper(system_power_action, a)
                    await speak_local(session, f"Executing {a}.")

                turn_ctx.pending_confirmation = {
                    "action": action,
                    "handler": _confirmed_power_action,
                    "requested_at": time.perf_counter(),
                }
                await speak_local(session, f"Are you sure you want to {action} the computer? Say yes to confirm.")
                return True

            print(f"[ROUTER] Direct command matched: system_power_action({action})")
            _abort_model_turn(session)
            await run_tool_helper(system_power_action, action)
            await speak_local(session, f"Executing {action}.")
            return True

        # System status / info
        if any(x in clean_command for x in ["system status", "system info", "battery", "cpu usage", "ram usage", "storage"]):
            print("[ROUTER] Direct command matched: get_system_status()")
            _abort_model_turn(session)
            result = await run_tool_helper(get_system_status)
            response = result if isinstance(result, str) else "System information retrieved."
            await speak_local(session, response[:300])
            return True

        # Show desktop
        if clean_command in ["show desktop", "go to desktop", "desktop"]:
            print("[ROUTER] Direct command matched: desktop_control(show)")
            _abort_model_turn(session)
            await run_tool_helper(desktop_control, "show")
            await speak_local(session, "Showing desktop.")
            return True

        # Virus scan
        if any(x in clean_command for x in ["virus scan", "scan for viruses", "malware scan", "security scan", "scan my system"]):
            print("[ROUTER] Direct command matched: scan_system_for_viruses()")
            _abort_model_turn(session)
            result = await run_tool_helper(scan_system_for_viruses)
            response = result if isinstance(result, str) else "Scan complete."
            await speak_local(session, response[:300])
            return True

        # Read screen
        if any(x in clean_command for x in ["read the screen", "read screen", "what's on screen", "read text on screen"]):
            print("[ROUTER] Direct command matched: read_screen_text()")
            _abort_model_turn(session)
            result = await run_tool_helper(read_screen_text)
            response = result if isinstance(result, str) else "Screen text read."
            await speak_local(session, response[:300])
            return True

        # Analyze screen
        if any(x in clean_command for x in ["analyze screen", "analyze my screen", "describe my screen", "what's on my screen"]):
            print("[ROUTER] Direct command matched: analyze_screen()")
            _abort_model_turn(session)
            result = await run_tool_helper(analyze_screen, clean_command)
            response = result if isinstance(result, str) else "Screen analyzed."
            await speak_local(session, response[:300])
            return True

        # Type text — "type hello world"
        type_match = re.search(r'^type\s+(.+)', clean_command)
        if type_match:
            text_to_type = type_match.group(1).strip()
            print(f"[ROUTER] Direct command matched: type_user_message_auto({text_to_type})")
            _abort_model_turn(session)
            await run_tool_helper(type_user_message_auto, text_to_type)
            await speak_local(session, "Typed.")
            return True

        # Keyboard shortcuts — undo, redo, select all
        if clean_command in ["undo"]:
            print("[ROUTER] Direct command matched: press_key(ctrl+z)")
            _abort_model_turn(session)
            await run_tool_helper(press_key, "ctrl+z")
            await speak_local(session, "Undone.")
            return True
        if clean_command in ["redo"]:
            print("[ROUTER] Direct command matched: press_key(ctrl+y)")
            _abort_model_turn(session)
            await run_tool_helper(press_key, "ctrl+y")
            await speak_local(session, "Redone.")
            return True
        if clean_command in ["select all", "select everything"]:
            print("[ROUTER] Direct command matched: press_key(ctrl+a)")
            _abort_model_turn(session)
            await run_tool_helper(press_key, "ctrl+a")
            await speak_local(session, "All selected.")
            return True

        # File conversions — word/excel/ppt/image to PDF
        if "to pdf" in clean_command:
            _abort_model_turn(session)
            if "word" in clean_command or "doc" in clean_command:
                print("[ROUTER] Direct command matched: word_to_pdf()")
                await run_tool_helper(word_to_pdf)
                await speak_local(session, "Converted Word to PDF.")
            elif "excel" in clean_command or "spreadsheet" in clean_command:
                print("[ROUTER] Direct command matched: excel_to_pdf()")
                await run_tool_helper(excel_to_pdf)
                await speak_local(session, "Converted Excel to PDF.")
            elif "powerpoint" in clean_command or "ppt" in clean_command:
                print("[ROUTER] Direct command matched: ppt_to_pdf()")
                await run_tool_helper(ppt_to_pdf)
                await speak_local(session, "Converted PowerPoint to PDF.")
            elif "image" in clean_command or "picture" in clean_command or "photo" in clean_command:
                print("[ROUTER] Direct command matched: image_to_pdf()")
                await run_tool_helper(image_to_pdf)
                await speak_local(session, "Converted image to PDF.")
            else:
                return False
            return True

        # Spotify liked songs (missed by existing Spotify block)
        if any(x in clean_command for x in ["play liked songs", "play my liked", "play favorites", "play my favorites"]):
            print("[ROUTER] Direct command matched: spotify_play_liked()")
            _abort_model_turn(session)
            await run_tool_helper(spotify_play_liked)
            await speak_local(session, "Playing your liked songs.")
            return True

        # Fix code error
        if any(x in clean_command for x in ["fix code error", "fix this error", "fix my code", "debug code"]):
            print("[ROUTER] Direct command matched: fix_code_error()")
            _abort_model_turn(session)
            result = await run_tool_helper(fix_code_error)
            response = result if isinstance(result, str) else "Code error fixed."
            await speak_local(session, response[:300])
            return True

    except Exception as e:
        router_logger.error(f"[ROUTER] Error executing direct tool: {e}", exc_info=True)
        # CRITICAL: reset turn state on error so the assistant isn't permanently wedged
        turn_ctx.state = "IDLE"
        log_turn_outcome(clean_command, "router_exception", "unknown", False, detail=str(e))

        _abort_model_turn(session)
        await speak_local(session, "Sorry, I encountered an error running that command.")
        update_gui_status("Listening...")
        return True

    return False

# Local file search helpers
def find_and_open_file(name_query, file_type="pdf"):
    import os
    dirs = [
        os.path.join(os.path.expanduser("~"), "Downloads"),
        os.path.join(os.path.expanduser("~"), "Documents"),
        os.path.join(os.path.expanduser("~"), "Desktop"),
        os.getcwd()
    ]
    # Check active explorer path
    # Removed slow PowerShell COM inspection to reduce latency.
    # We now strictly search standard user directories directly.
        
    for d in dirs:
        if not os.path.exists(d):
            continue
        for root, _, files in os.walk(d):
            if root.count(os.sep) - d.count(os.sep) > 1:
                continue
            for f in files:
                if name_query.lower() in f.lower():
                    if file_type == "pdf" and f.lower().endswith(".pdf"):
                        path = os.path.join(root, f)
                        try:
                            os.startfile(path)
                        except:
                            import subprocess
                            subprocess.Popen(["explorer", path])
                        return path
                    elif file_type == "any":
                        path = os.path.join(root, f)
                        try:
                            os.startfile(path)
                        except:
                            import subprocess
                            subprocess.Popen(["explorer", path])
                        return path
    return None

def extract_pdf_page(file_path, page_num):
    try:
        import PyPDF2
        with open(file_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            if page_num < len(reader.pages):
                page = reader.pages[page_num]
                return page.extract_text() or "(No text could be extracted from this page)"
            else:
                return f"Page {page_num+1} out of range. The document has {len(reader.pages)} pages."
    except Exception as e:
        return f"Could not read PDF page: {e}"

def reset_active_timeout(session):
    global active_timeout_task
    if active_timeout_task:
        active_timeout_task.cancel()
    
    current_turn_id = turn_ctx.turn_id
    async def timeout_coro(turn_id):
        await asyncio.sleep(8)
        global turn_ctx
        # Only deactivate if the turn hasn't changed
        if turn_ctx.is_active and turn_ctx.turn_id == turn_id:
            print("[ROUTER] Active listening timeout. Deactivating...")
            turn_ctx.is_active = False
            update_gui_status("Listening...")
            
    active_timeout_task = asyncio.create_task(timeout_coro(current_turn_id))

async def handle_user_transcript(session: AgentSession, transcript: str):
    global turn_ctx, active_timeout_task
    clean_text = transcript.strip().lower()
    print(f"[ROUTER] received: {clean_text}")
    print(f"[VOICE] User speech transcript: '{clean_text}' (is_active={turn_ctx.is_active})")

    now = time.perf_counter()

    # --- TIMEOUT BACKSTOP ---
    # If _turn_in_progress has been True for longer than 30s, force-reset it.
    # This prevents the assistant from being permanently wedged if a turn
    # completes without reaching any of the normal reset paths.
    if turn_ctx.state != 'IDLE' and (now - turn_ctx.last_handled_at) > 30.0:
        print(f"[ROUTER] SAFETY RESET — _turn_in_progress stuck for {now - turn_ctx.last_handled_at:.1f}s, force-clearing")
        turn_ctx.state = "IDLE"
        

    if turn_ctx.state != 'IDLE':
        print(f"[ROUTER] PREEMPTING previous turn ({turn_ctx.state}) for new command: {clean_text}")
        _abort_model_turn(session)
        # We don't return here! We allow the new command to become the active turn.

    # --- EXACT DUPLICATE suppression (same transcript within 6s) ---
    if clean_text and clean_text == turn_ctx.last_handled_transcript and (now - turn_ctx.last_handled_at) < 3.0:
        print("[ROUTER] ignored — duplicate transcript of completed task")
        _abort_model_turn(session)
        return

    # --- ECHO suppression (mic picks up Tony's own speech) ---
    # FIXED: Was using bidirectional substring match which falsely ate short
    # commands like "play" if Tony had said "playing music on spotify".
    # Now uses SequenceMatcher ratio >= 0.85 (near-exact match only) with
    # a tighter 4s window instead of 8s.
    if turn_ctx.last_spoken_text and clean_text and (now - turn_ctx.last_handled_at) < 2.0:
        echo_ratio = difflib.SequenceMatcher(None, clean_text, turn_ctx.last_spoken_text).ratio()
        if echo_ratio >= 0.85:
            print(f"[ROUTER] ignored — echo of Tony's last spoken line (similarity={echo_ratio:.2f})")
            _abort_model_turn(session)
            return

    if _is_repeated_command(clean_text, now):
        _abort_model_turn(session)
        return

    timer = get_or_create_timer()
    timer.t4 = time.perf_counter()
    print("[T4] command router started")

    wake_word_match = re.search(r'^\s*(?:hey\s+)?tony\b[\s,:]*', clean_text)
    if wake_word_match:
        command_after = clean_text[wake_word_match.end():].strip()
        if not command_after:
            # User only said "Tony" or "Hey Tony"
            _abort_model_turn(session)
            update_gui_status("Speaking...")
            await speak_local(session, "Yes, I am listening!")
            return
        effective_command = command_after
    else:
        effective_command = clean_text

    if active_timeout_task:
        active_timeout_task.cancel()

    turn_ctx.next_turn()  # Increment turn_id to cancel any lingering LLM background tools
    
    # CRITICAL: Abort Gemini's native audio auto-response BEFORE the direct router
    # runs. This prevents the race condition where both Gemini's native response AND
    # the direct router (or generate_reply fallback) produce duplicate bubbles.
    _abort_model_turn(session)
    
    update_gui_status("Executing...")
    turn_ctx.state = "ROUTING"
    turn_ctx.last_handled_at = time.perf_counter()
    handled = await route_command_directly(session, effective_command)
    if handled:
        print("[ROUTER] Direct command handled")
        turn_ctx.last_handled_transcript = clean_text
        turn_ctx.last_handled_at = time.perf_counter()
        _finish_direct_turn(session)
    else:
        print(f"[ROUTER] Direct routing failed, generating reply via LLM for: '{clean_text}'")
        turn_ctx.state = "LLM_EXECUTION"
        update_gui_status("Processing...")
        timer.t5 = time.perf_counter()
        print("[T5] LLM request started (sole response path - native audio already aborted)")
        await _generate_reply_with_retry(session, transcript)
        turn_ctx.last_handled_transcript = clean_text
        turn_ctx.last_handled_at = time.perf_counter()
        # CRITICAL FIX: the LLM-fallback branch previously never reset
        # turn_ctx.state back to IDLE (only the direct-router branch did, via
        # _finish_direct_turn). That left state stuck at "LLM_EXECUTION" after
        # any Gemini-routed command, so every subsequent turn hit the
        # "PREEMPTING previous turn" path and the assistant felt wedged until
        # the 30s safety backstop fired — exactly the "works for 2-3 commands
        # then gets stuck in a loop" symptom. Always return to idle listening
        # here so follow-up commands route cleanly.
        _finish_direct_turn(session)

# =========================
# GEMINI RETRY / GRACEFUL DEGRADATION
# =========================
# Tracks consecutive Gemini failures so we can surface a one-time spoken
# notice when entering degraded mode, and re-check reachability on each
# call rather than trusting a single import-time flag forever.
_gemini_consecutive_failures = 0
_gemini_degraded_mode = False
_GEMINI_DEGRADED_THRESHOLD = 2  # consecutive failures before announcing degraded mode


async def _generate_reply_with_retry(session: AgentSession, transcript: str, max_retries: int = 1) -> bool:
    """
    Call session.generate_reply() with one retry-with-backoff on failure.
    On repeated failure, degrade gracefully: tell the user complex
    requests are temporarily limited but direct commands still work,
    rather than hanging or returning a bare generic error every time.
    """
    global _gemini_consecutive_failures, _gemini_degraded_mode

    attempt = 0
    last_error = None
    while attempt <= max_retries:
        try:
            await session.generate_reply(
                instructions=f"The user said: '{transcript}'. Respond concisely, directly and helpfully."
            )
            if _gemini_consecutive_failures > 0:
                router_logger.info("[GEMINI] Recovered after previous failure(s)")
            _gemini_consecutive_failures = 0
            _gemini_degraded_mode = False
            return True
        except Exception as e:
            last_error = e
            attempt += 1
            if attempt <= max_retries:
                backoff_seconds = 0.5 * attempt
                router_logger.warning(f"[GEMINI] generate_reply failed (attempt {attempt}/{max_retries + 1}): {e}. Retrying in {backoff_seconds:.1f}s")
                await asyncio.sleep(backoff_seconds)

    _gemini_consecutive_failures += 1
    router_logger.error(f"[GEMINI] generate_reply failed after {max_retries + 1} attempt(s): {last_error}", exc_info=True)
    log_turn_outcome(transcript, "llm_fallback", "generate_reply", False, detail=str(last_error))

    if _gemini_consecutive_failures >= _GEMINI_DEGRADED_THRESHOLD and not _gemini_degraded_mode:
        _gemini_degraded_mode = True
        network_up = await asyncio.get_running_loop().run_in_executor(None, is_network_reachable)
        if network_up:
            notice = (
                "I'm having trouble reaching my AI engine right now. Direct commands like opening apps, "
                "volume, and screenshots will still work, but complex requests are temporarily limited."
            )
        else:
            notice = (
                "It looks like the network connection is down. Direct commands will still work, "
                "but I can't reach the AI engine for complex requests until the connection is back."
            )
        await speak_local(session, notice)
    else:
        await speak_local(session, "I heard you, but I couldn't process that command.")

    _finish_direct_turn(session)
    return False

_global_llm = None

def _init_global_llm():
    global _global_llm
    if _global_llm is None:
        if network_available:
            print("🧠 Initializing Gemini Realtime LLM once...")
            _global_llm = RealtimeModel(
                model="gemini-2.5-flash-native-audio-preview-12-2025",
                voice="Aoede",  # Female voice
                temperature=0.8,
                max_output_tokens=768,
            )
        else:
            raise ValueError(f"RealtimeModel not available. Import error: {import_error}")
    return _global_llm

# =========================
# MAIN AGENT
# =========================
class UltimateAdvancedTony(Agent):
    def __init__(self):
        import tools
        tools.assistant_instance = self
        self._reminders: Dict[str, Dict[str, Any]] = {}
        self._reminder_task: Optional[asyncio.Task] = None
        self._session: Optional[AgentSession] = None
        self._reminder_counter = 0
        self._scheduled_tasks: Dict[str, Dict[str, Any]] = {}
        self._scheduler_task: Optional[asyncio.Task] = None
        self._task_counter = 0

        # DYNAMIC TOOL GROUPING: We only send essential LLM-oriented tools to reduce context/latency.
        # Direct UI/System commands are handled by the Direct Router anyway.
        tools = [
            search_web, get_weather, get_top_news, web_scraper,
            generate_and_type_code, fix_code_error,
            generate_ai_image, 
            process_document_query,
            analyze_screen, analyze_local_image, extract_text_from_image,
            write_in_notepad, create_essay_in_notepad,
            set_reminder, schedule_task,
            execute_multi_task,
            # Workstream 3 coverage tools — these have no dedicated direct-router
            # intent, so they must go to the LLM to be reachable at all.
            write_document, edit_existing_file,
            create_presentation, edit_presentation,
            enter_excel_formula, create_excel_chart,
            rename_file_or_folder, move_file_or_folder, copy_file_or_folder,
            delete_file_or_folder, search_files_by_content, zip_paths, unzip_archive,
            batch_rename,
            browser_automate,
            send_email,
            perform_computer_action,
        ]

        wrapped_tools = [make_timing_decorator(t) for t in tools]
        super().__init__(
            instructions=self._build_instructions(),
            tools=wrapped_tools,
            llm=self._init_llm(),
            min_endpointing_delay=0.05,
            max_endpointing_delay=0.20,
            vad=silero.VAD.load(
                activation_threshold=0.3,
                deactivation_threshold=0.25,
                min_speech_duration=0.03,
                min_silence_duration=0.25
            ),
        )

        print(f"[OK] Tony initialized with {len(tools)} tools")

    def _init_llm(self):
        global _global_llm
        if _global_llm is None:
            _global_llm = _init_global_llm()
        return _global_llm

    def _build_instructions(self):
        return "\n".join([
            AGENT_INSTRUCTION,
            AGENT_INSTRUCTION_FOR_TOOLS,
            "You have access to ALL system, voice, automation and reminder tools.",
            "Use tools aggressively when required.",
        ])

    # =========================
    # REMINDER SYSTEM
    # =========================
    def set_session(self, session: AgentSession):
        self._session = session
        print("🔔 Session linked for reminders")

    def add_reminder(self, reminder_text: str, reminder_time: datetime, reminder_type: str = "message"):
        rid = f"rem_{self._reminder_counter}"
        self._reminder_counter += 1

        self._reminders[rid] = {
            "text": reminder_text,
            "time": reminder_time,
        }

        if not self._reminder_task or self._reminder_task.done():
            self._reminder_task = asyncio.create_task(self._monitor_reminders())

        return rid

    def get_reminders(self):
        return {
            rid: {
                "reminder_text": data["text"],
                "reminder_time": data["time"]
            }
            for rid, data in self._reminders.items()
        }

    def cancel_reminder(self, reminder_id: str) -> bool:
        if reminder_id in self._reminders:
            self._reminders.pop(reminder_id)
            return True
        return False

    async def _monitor_reminders(self):
        print("⏰ Reminder monitor running")
        while self._reminders:
            now = datetime.now()
            triggered = []

            for rid, data in self._reminders.items():
                if now >= data["time"]:
                    await self._trigger_reminder(data["text"])
                    triggered.append(rid)

            for rid in triggered:
                self._reminders.pop(rid, None)

            await asyncio.sleep(5)

    async def _trigger_reminder(self, text: str):
        if self._session:
            await self._session.generate_reply(
                instructions=f"Reminder: {text}"
            )
            print(f"🔔 Reminder sent → {text}")

    # =========================
    # TASK SCHEDULER SYSTEM
    # =========================
    def add_scheduled_task(self, task_description: str, schedule_time: datetime, tool_name: str, tool_parameters: str = ""):
        tid = f"task_{self._task_counter}"
        self._task_counter += 1

        self._scheduled_tasks[tid] = {
            "task_description": task_description,
            "schedule_time": schedule_time,
            "tool_name": tool_name,
            "tool_parameters": tool_parameters,
        }

        if not self._scheduler_task or self._scheduler_task.done():
            self._scheduler_task = asyncio.create_task(self._monitor_scheduled_tasks())

        return tid

    def get_scheduled_tasks(self):
        return self._scheduled_tasks

    def cancel_scheduled_task(self, task_id: str) -> bool:
        if task_id in self._scheduled_tasks:
            self._scheduled_tasks.pop(task_id)
            return True
        return False

    async def _monitor_scheduled_tasks(self):
        print("⏰ Scheduler monitor running")
        while self._scheduled_tasks:
            now = datetime.now()
            triggered = []

            for tid, data in list(self._scheduled_tasks.items()):
                if now >= data["schedule_time"]:
                    await self._execute_scheduled_task(data)
                    triggered.append(tid)

            for tid in triggered:
                self._scheduled_tasks.pop(tid, None)

            await asyncio.sleep(5)

    async def _execute_scheduled_task(self, task_data: dict):
        tool_name = task_data["tool_name"]
        params = task_data["tool_parameters"]
        desc = task_data["task_description"]
        print(f"🚀 Executing scheduled task: {desc} ({tool_name})")
        
        try:
            # Map tools dynamically from already imported functions
            tool_mapping = {
                "open_app": open_app,
                "search_web": search_web,
                "send_whatsapp_message": send_whatsapp_message,
                "control_system_volume": control_system_volume,
                "control_screen_brightness": control_screen_brightness,
                "play_media": play_media,
                "write_in_notepad": write_in_notepad,
            }
            
            if tool_name in tool_mapping:
                fn = tool_mapping[tool_name]
                if asyncio.iscoroutinefunction(fn):
                    import inspect
                    sig = inspect.signature(fn)
                    if len(sig.parameters) > 0:
                        res = await fn(params)
                    else:
                        res = await fn()
                else:
                    import inspect
                    sig = inspect.signature(fn)
                    if len(sig.parameters) > 0:
                        res = fn(params)
                    else:
                        res = fn()
                msg = f"Scheduled task executed successfully: {res}"
            else:
                msg = f"Scheduled task triggered, but tool '{tool_name}' is not dispatchable."
            
            await self._trigger_reminder(msg)
        except Exception as e:
            print(f"[ERROR] Error executing scheduled task: {e}")
            await self._trigger_reminder(f"Failed to execute scheduled task '{desc}': {e}")

# =========================
# STARTUP SELF-CHECK
# =========================
def _run_startup_self_check() -> None:
    """
    Verify LiveKit credentials, Gemini reachability, and OS automation
    permissions up front, surfacing one clear actionable summary instead
    of failing silently deep into a later turn. Never raises or blocks
    startup — this is diagnostic, not a hard gate, since some permissions
    (e.g. OCR) are optional-feature-only.
    """
    issues = []

    # 1. LiveKit credentials
    missing_livekit = [v for v in ("LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET") if not os.getenv(v)]
    if missing_livekit:
        issues.append(f"LiveKit credentials missing: {', '.join(missing_livekit)}. Voice sessions will not connect.")

    # 2. Gemini / AI provider reachability
    if not network_available:
        issues.append(f"Gemini Realtime SDK failed to import: {import_error}. LLM fallback will be unavailable.")
    elif not os.getenv("GOOGLE_API_KEY"):
        issues.append("GOOGLE_API_KEY is not set. Gemini Realtime will fail to authenticate.")
    else:
        reachable = is_network_reachable()
        if not reachable:
            issues.append("Network connectivity check failed (could not reach 8.8.8.8:53). Gemini calls may fail until connectivity is restored.")

    # 3. OS automation permissions (OCR dependency used by click_on_text / perform_computer_action's click_text)
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
    except ImportError:
        issues.append("pytesseract is not installed. OCR-based screen-text/click features will be unavailable.")
    except Exception:
        issues.append(
            "Tesseract OCR binary not found on PATH. OCR-based 'click the X button' features will be "
            "unavailable until it's installed (see README)."
        )

    if issues:
        router_logger.warning("[STARTUP SELF-CHECK] " + " | ".join(issues))
        print("\n[STARTUP SELF-CHECK] Potential issues detected:")
        for i, issue in enumerate(issues, 1):
            print(f"  {i}. {issue}")
        print("[STARTUP SELF-CHECK] Tony will still start, but the above features may not work.\n")
    else:
        router_logger.info("[STARTUP SELF-CHECK] All checks passed.")
        print("[STARTUP SELF-CHECK] All checks passed.")


# =========================
# ENTRYPOINT
# =========================
_greeting_sent = False

async def entrypoint(ctx: agents.JobContext):
    # Ignore handshake-room job assignments
    if ctx.room.name == "handshake-room":
        print("[INFO] Ignoring handshake-room job request.")
        return

    print("[INFO] Starting Tony...")
    _run_startup_self_check()
    global active_session, background_loop, active_room, worker_loop
    active_room = ctx.room
    worker_loop = asyncio.get_running_loop()
    setup_rpc_proxies()

    update_gui_connection("LiveKit: Connecting... | Gemini: Offline")

    agent = UltimateAdvancedTony()
    session = AgentSession()
    active_session = session
    background_loop = worker_loop

    # Event registration on session to route events to GUI and log performance
    @session.on("user_state_changed")
    def on_user_state_changed(ev: agents.voice.UserStateChangedEvent):
        timer = get_or_create_timer()
        if ev.new_state == "speaking":
            reset_timer()
            timer = get_or_create_timer()
            timer.t1 = time.perf_counter()
            print("[T1] speech started")
            print("[VAD] speech detected")
            update_gui_status("Speech Detected")
            # INTERRUPTION: If TONY is currently speaking, stop it
            if is_speaking_locally:
                try:
                    session.interrupt(force=True)
                except Exception:
                    pass
        elif ev.new_state == "idle":
            timer.t2 = time.perf_counter()
            print("[T2] speech ended")
            print("[VAD] speech ended")
            update_gui_status("Transcribing...")

    @session.on("user_input_transcribed")
    def on_user_transcript(ev: agents.voice.UserInputTranscribedEvent):
        global is_speaking_locally, last_local_speech_end
        if is_speaking_locally or (time.perf_counter() - last_local_speech_end < 0.8):
            return
        if ev.transcript.strip():
            # Stream partial/final transcript into a single bubble
            update_gui_partial_transcript(ev.transcript, ev.is_final)
            if ev.is_final:
                timer = get_or_create_timer()
                timer.t3 = time.perf_counter()
                timer.command = ev.transcript
                print(f"[T3] transcript received: '{ev.transcript}'")
                print(f"[STT] transcript received: {ev.transcript}")

                asyncio.create_task(handle_user_transcript(session, ev.transcript))
    @session.on("agent_state_changed")
    def on_agent_state(ev: agents.voice.AgentStateChangedEvent):
        print(f"[AGENT] State changed: {ev.old_state} -> {ev.new_state}")
        timer = get_or_create_timer()

        if ev.new_state in ["listening", "idle"]:
            global turn_ctx
            turn_ctx.state = "IDLE"
            
            
            update_gui_status("Listening...")
        elif ev.new_state == "thinking":
            update_gui_status("Thinking...")
            timer.t5 = time.perf_counter()
            print("[T5] LLM request started")
            print("[LLM] request started")
        elif ev.new_state == "speaking":
            update_gui_status("Speaking...")
            timer.t6 = time.perf_counter()
            timer.t9 = time.perf_counter()
            print("[T6] LLM response received")
            print("[T9] response started")
            print("[LLM] response received")
            # Log LLM-fallback path timing breakdown
            if timer.t4 and timer.t5 and timer.t6:
                print(f"[PERF-LLM] Transcript→Router: {timer.t5 - timer.t4:.3f}s")
                print(f"[PERF-LLM] Router→LLM-response: {timer.t6 - timer.t5:.3f}s")
                if timer.t3:
                    print(f"[PERF-LLM] Total transcript→response: {timer.t6 - timer.t3:.3f}s")

        # Log response completed when transitioning out of speaking
        if ev.old_state == "speaking" and ev.new_state != "speaking":
            timer.t10 = time.perf_counter()
            print("[T10] response completed")
            timer.print_perf()
    _last_convo_text = ""
    _last_convo_time = 0.0

    @session.on("conversation_item_added")
    def on_convo_item(ev: agents.voice.ConversationItemAddedEvent):
        nonlocal _last_convo_text, _last_convo_time
        if hasattr(ev.item, "role") and ev.item.role == "assistant":
            # Skip GUI updates for direct router's session.say() to avoid duplicate text bubbles
            if is_speaking_locally:
                print("[CONVO] Skipped GUI update — direct router already rendered text")
                return

            # Extract content from ChatMessage
            text = ""
            if hasattr(ev.item, "content"):
                content = ev.item.content
                if isinstance(content, str):
                    text = content
                elif isinstance(content, list):
                    texts = []
                    for block in content:
                        if isinstance(block, str):
                            texts.append(block)
                        elif hasattr(block, "text"):
                            texts.append(block.text)
                        elif isinstance(block, dict) and "text" in block:
                            texts.append(block["text"])
                    text = " ".join(texts)

            if text:
                # Dedup: skip if same text rendered within 3 seconds
                now = time.perf_counter()
                if text.strip() == _last_convo_text.strip() and (now - _last_convo_time) < 3.0:
                    print(f"[CONVO] Skipped duplicate bubble: '{text[:40]}...'")
                    return
                _last_convo_text = text
                _last_convo_time = now
                update_gui_response(text)

            global turn_ctx
            turn_ctx.state = "IDLE"

    @session.on("close")
    def on_session_close(ev: agents.voice.CloseEvent):
        update_gui_connection("LiveKit: Disconnected | Gemini: Offline")
        update_gui_status("Offline")
        agent_listening_flag.clear()

    try:
        await session.start(
            room=ctx.room,
            agent=agent,
            room_input_options=RoomInputOptions(
                video_enabled=False,
                noise_cancellation=noise_cancellation.BVC(),
            ),
        )

        # Record T0
        timer = get_or_create_timer()
        timer.t0 = time.perf_counter()
        print("[T0] microphone detected")

        agent.set_session(session)

        await ctx.connect()
        update_gui_connection("LiveKit: Connected | Gemini: Active")
        update_gui_status("Listening...")
        agent_listening_flag.set()

        # Load conversation history into GUI (non-blocking)
        asyncio.create_task(_load_history_to_gui())

        # Start session health monitor for 2-hour sessions
        asyncio.create_task(_session_health_monitor())

        global _greeting_sent
        if not _greeting_sent:
            _greeting_sent = True
            await session.generate_reply(instructions=SESSION_INSTRUCTION)
        print("[INFO] Tony is LIVE & READY")
    except Exception as conn_err:
        print(f"[ERROR] LiveKit session start failed: {conn_err}")
        import traceback
        traceback.print_exc()
        update_gui_connection(f"Error: {str(conn_err)[:35]}")
        update_gui_status("Offline")
        return

    try:
        await asyncio.Future()
    except asyncio.CancelledError:
        print("[INFO] Tony stopped")


async def _load_history_to_gui():
    """Load recent conversation history from SQLite DB into GUI chat bubbles."""
    try:
        await asyncio.sleep(1.5)  # Small delay — let GUI settle first
        from memory_db import MemoryDatabase
        db = MemoryDatabase()
        history = db.get_conversation_history(limit=20)
        if not history:
            return
        print(f"[HISTORY] Loading {len(history)} conversation turns into GUI")
        # history is newest-first; reverse for chronological display
        cb = _gui_callbacks.get('add_static_bubble')
        if not cb:
            return
        for conv in reversed(history):
            sender = "You" if conv.role == "user" else "TONY"
            content = conv.content.strip()
            if content:
                try:
                    cb(sender, content[:250])
                    await asyncio.sleep(0.02)  # Tiny gap so Qt can process each
                except Exception:
                    pass
        print("[HISTORY] History loaded into GUI")
    except Exception as e:
        print(f"[HISTORY] Failed to load history: {e}")


async def _session_health_monitor():
    """Runs every 30 minutes to keep session memory bounded for 2-hour sessions."""
    global latency_history
    while True:
        await asyncio.sleep(1800)   # 30 minutes
        uptime_min = (time.perf_counter() - (current_timer.t0 if current_timer else time.perf_counter())) / 60
        print(f"[HEALTH] Session uptime: {uptime_min:.1f} min | "
              f"Latency samples: {len(latency_history)} | "
              f"Memory OK")
        # Prune latency history to prevent unbounded growth
        if len(latency_history) > 100:
            latency_history = latency_history[-50:]
            print("[HEALTH] Pruned latency_history to last 50 samples")

if __name__ == "__main__":
    import sys
    # If starting as worker, run LiveKit runner directly in console mode
    if len(sys.argv) > 1 and sys.argv[1] in ["dev", "start", "agent"]:
        print("[OK] Starting TONY agent worker in console mode...")
        from livekit.agents.cli import run_app
        from livekit.agents import WorkerOptions, JobExecutorType
        run_app(WorkerOptions(entrypoint_fnc=entrypoint, job_executor_type=JobExecutorType.THREAD))
    else:
        # Default: run GUI
        sys.argv = [sys.argv[0]]
        print("[OK] TONY GUI starting...")
        
        # Import and run Tony interface
        import Tony
        sys.exit(Tony.main())
