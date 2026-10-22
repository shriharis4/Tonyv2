"""
Tools facade module for Tony assistant.

Re-exports every canonical tool implementation from `tool_registry.py`,
the single source of truth for tool registration. Both this module and
`core/runtime_agent.py` import from `tool_registry` so a tool can never be
added to one path and silently missing from the other.
"""

# Global assistant instance reference accessed by Tools/reminder.py and Tools/schedule_task.py
assistant_instance = None

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
)
