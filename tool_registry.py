"""
Single source of truth for Tony's tool registration.

Every automation/productivity function lives in `Tools/`. Historically both
`tools.py` (a facade module) and `core/runtime_agent.py` independently imported
every tool, which meant a tool added to one list and not the other would
silently never reach Gemini's function-calling schema. This module collapses
those two import lists into one: both `tools.py` and `core/runtime_agent.py`
now import from here.

Usage:
    from tool_registry import TOOLS, TOOL_CATEGORY, get_all_tool_functions

`TOOLS` is a flat namespace-style import of every public tool callable.
`TOOL_CATEGORY` maps function name -> category string, used by
`execute_tool()` in `core/runtime_agent.py` to pick a timeout tier
(in_process / app_launch / network).
`get_all_tool_functions()` returns the list of callables to hand to the
LLM's function-calling tool registration.
"""

from __future__ import annotations

# =========================
# CANONICAL TOOL IMPORTS
# (the only place these should be imported from Tools/*)
# =========================
from Tools.manage_windows import manage_window, list_windows
from Tools.search_web import search_web
from Tools.send_whatsapp_message import send_whatsapp_message, send_whatsapp_message_advanced
from Tools.system_power_action import system_power_action
from Tools.type_user_message_auto import (
    type_user_message_auto,
    create_essay_in_notepad,
    write_essay_in_notepad,
)
from Tools.write_in_notepad import write_in_notepad
from Tools.desktop_control import desktop_control
from Tools.scroll_content import scroll_content
from Tools.code_handler import fix_code_error
from Tools.file_searching import universal_file_opener
from Tools.press_key import press_key, use_smart_clipboard
from Tools.open_app import open_app
from Tools.scan_system_for_viruses import scan_system_for_viruses
from Tools.time_volume_bright import (
    control_screen_brightness,
    control_system_volume,
    get_time_info,
    get_weather,
    get_system_info_deep,
    get_current_volume,
    get_system_status,
)
from Tools.multi_task import execute_multi_task
from Tools.generate_ai_image import generate_ai_image
from Tools.code_generator import generate_and_type_code, run_file_in_vscode
from Tools.news_provider import get_top_news
from Tools.youtube_videos import play_media
from Tools.reminder import set_reminder, view_reminders, cancel_reminder
from Tools.screen_short import screen_short
from Tools.pdf_reader import process_document_query
from Tools.send_media_whatsapp import send_media_to_whatsapp
from Tools.excel_data_entery import (
    create_excel_file,
    save_excel_changes,
    delete_all_data,
    move_left,
    move_up,
    enter_data_quick,
    enter_multiple_data_quick,
    move_down,
    move_right,
    delete_current_cell,
    go_to_cell,
    toggle_text_bold,
    select_row_or_column,
    sort_excel_data,
    excel_clipboard_action,
    calculate_sum,
    enter_excel_formula,
    create_excel_chart,
)
from Tools.word_to_pdf import (
    word_to_pdf,
    image_to_pdf,
    excel_to_pdf,
    ppt_to_pdf,
    convert_image_format,
    test_converters,
)
from Tools.create_folder import create_here
from Tools.read_screen_text import read_screen_text
from Tools.camera_analysis import camera_analysis
from Tools.screen_analyzer import analyze_screen
from Tools.image_analysis import (
    analyze_local_image,
    identify_objects_in_image,
    extract_text_from_image,
    analyze_photo_composition,
    detect_image_authenticity,
    describe_image_for_visually_impaired,
    get_image_color_analysis,
    compare_images,
)
from Tools.spotify import (
    open_spotify,
    spotify_next,
    spotify_previous,
    spotify_play_song,
    spotify_play_liked,
    spotify_pause,
    spotify_play,
)
from Tools.click_on_text import click_on_screen_text, click_text, find_all_text, verify_ocr_setup
from Tools.schedule_task import schedule_task, view_scheduled_tasks, cancel_scheduled_task
from Tools.webScrping import web_scraper
from Tools.computer_use import perform_computer_action

# --- New Workstream 3 coverage tools ---
from Tools.document_writer import write_document, edit_existing_file
from Tools.powerpoint_tool import create_presentation, edit_presentation
from Tools.file_ops import (
    rename_file_or_folder,
    move_file_or_folder,
    copy_file_or_folder,
    delete_file_or_folder,
    search_files_by_content,
    zip_paths,
    unzip_archive,
    batch_rename,
)
from Tools.browser_automation import browser_automate
from Tools.send_email import send_email


# =========================
# TOOL -> TIMEOUT CATEGORY MAP
# =========================
# "in_process"  -> ~2s  (pure Python / in-memory, keyboard/mouse single actions)
# "app_launch"  -> ~8s  (subprocess spawn, app launch, file IO, office automation)
# "network"     -> ~15s (web search, weather, news, scraping, email, browser automation)
TOOL_CATEGORY: dict[str, str] = {}


def _mark(category: str, *funcs):
    for f in funcs:
        name = getattr(f, "__name__", None)
        if name:
            TOOL_CATEGORY[name] = category


_mark(
    "in_process",
    manage_window, list_windows, desktop_control, scroll_content, press_key,
    use_smart_clipboard, control_screen_brightness, control_system_volume,
    get_time_info, get_current_volume, read_screen_text, click_on_screen_text,
    click_text, find_all_text, verify_ocr_setup, type_user_message_auto,
    get_system_info_deep, get_system_status,
)

_mark(
    "app_launch",
    open_app, system_power_action, write_in_notepad, create_essay_in_notepad,
    write_essay_in_notepad, create_here, screen_short, create_excel_file,
    save_excel_changes, delete_all_data, move_left, move_up, move_down, move_right,
    enter_data_quick, enter_multiple_data_quick, delete_current_cell, go_to_cell,
    toggle_text_bold, select_row_or_column, sort_excel_data, excel_clipboard_action,
    calculate_sum, enter_excel_formula, create_excel_chart, word_to_pdf, image_to_pdf,
    excel_to_pdf, ppt_to_pdf, convert_image_format, test_converters, open_spotify,
    spotify_next, spotify_previous,
    spotify_pause, spotify_play, run_file_in_vscode, generate_and_type_code,
    fix_code_error, scan_system_for_viruses, camera_analysis, analyze_screen,
    analyze_local_image, identify_objects_in_image, extract_text_from_image,
    analyze_photo_composition, detect_image_authenticity,
    describe_image_for_visually_impaired, get_image_color_analysis, compare_images,
    universal_file_opener, process_document_query, execute_multi_task,
    perform_computer_action, write_document, edit_existing_file,
    create_presentation, edit_presentation, rename_file_or_folder,
    move_file_or_folder, copy_file_or_folder, delete_file_or_folder,
    zip_paths, unzip_archive, batch_rename,
)

# Multi-step GUI automation flows that launch/focus an app and then drive
# its UI with timed keystrokes - these need a longer timeout (25s) so the
# render-wait + keypress sequence is never cut off mid-action (which would
# leave e.g. a song searched-but-not-playing).
_mark(
    "ui_automation",
    spotify_play_song, spotify_play_liked,
    send_whatsapp_message, send_whatsapp_message_advanced, send_media_to_whatsapp,
)

_mark(
    "network",
    search_web, get_weather, get_top_news, play_media, web_scraper,
    generate_ai_image, schedule_task, view_scheduled_tasks, cancel_scheduled_task,
    set_reminder, view_reminders, cancel_reminder, search_files_by_content,
    browser_automate, send_email,
)

# Default for anything not explicitly categorized above.
DEFAULT_TOOL_CATEGORY = "app_launch"


def get_tool_timeout(func_name: str) -> float:
    """Return the timeout (seconds) for a given tool function name."""
    category = TOOL_CATEGORY.get(func_name, DEFAULT_TOOL_CATEGORY)
    return {
        "in_process": 2.0,
        "app_launch": 8.0,
        "network": 15.0,
        # Multi-step GUI automation flows (launch app + wait for render +
        # drive the UI with keystrokes) legitimately take longer than a
        # simple app launch. Give them headroom so execute_tool's timeout
        # never kills the flow mid-playback / mid-send.
        "ui_automation": 25.0,
    }.get(category, 8.0)


# =========================
# FULL LIST OF TOOL CALLABLES FOR LLM FUNCTION-CALLING REGISTRATION
# =========================
def get_all_tool_functions() -> list:
    """Return every tool callable that should be registered with the LLM."""
    return [
        manage_window, list_windows, search_web, send_whatsapp_message,
        send_whatsapp_message_advanced, system_power_action, type_user_message_auto,
        create_essay_in_notepad, write_essay_in_notepad, write_in_notepad,
        desktop_control, scroll_content, fix_code_error, universal_file_opener,
        press_key, use_smart_clipboard, open_app, scan_system_for_viruses,
        control_screen_brightness, control_system_volume, get_time_info, get_weather,
        get_system_info_deep, get_current_volume, get_system_status,
        execute_multi_task, generate_ai_image, generate_and_type_code,
        run_file_in_vscode, get_top_news, play_media, set_reminder, view_reminders,
        cancel_reminder, screen_short, process_document_query, send_media_to_whatsapp,
        create_excel_file, save_excel_changes, delete_all_data, move_left, move_up,
        enter_data_quick, enter_multiple_data_quick, move_down, move_right,
        delete_current_cell, go_to_cell, toggle_text_bold, select_row_or_column,
        sort_excel_data, excel_clipboard_action, calculate_sum, enter_excel_formula,
        create_excel_chart, word_to_pdf, image_to_pdf, excel_to_pdf, ppt_to_pdf,
        convert_image_format, test_converters, create_here, read_screen_text,
        camera_analysis, analyze_screen, analyze_local_image, identify_objects_in_image,
        extract_text_from_image, analyze_photo_composition, detect_image_authenticity,
        describe_image_for_visually_impaired, get_image_color_analysis, compare_images,
        open_spotify, spotify_next, spotify_previous, spotify_play_song,
        spotify_play_liked, spotify_pause, spotify_play, click_on_screen_text,
        click_text, find_all_text, verify_ocr_setup, schedule_task,
        view_scheduled_tasks, cancel_scheduled_task, web_scraper, perform_computer_action,
        # Workstream 3 additions
        write_document, edit_existing_file, create_presentation, edit_presentation,
        rename_file_or_folder, move_file_or_folder, copy_file_or_folder,
        delete_file_or_folder, search_files_by_content, zip_paths, unzip_archive,
        batch_rename, browser_automate, send_email,
    ]
