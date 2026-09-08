"""
Tools facade module for Tony assistant.
Delegates all tool implementations directly to the canonical per-action modules in Tools/
to eliminate duplication and ensure consistent execution.
"""

# Global assistant instance reference accessed by Tools/reminder.py and Tools/schedule_task.py
assistant_instance = None

# Re-export all canonical implementations from Tools/
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
