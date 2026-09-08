import pyperclip
import pyautogui
import time
from livekit.agents import function_tool

@function_tool()
async def read_screen_text() -> str:
    """
    Reads text from screen using copy-paste method.
    
    Returns:
        str: The text extracted from screen or error message.
    """
    try:
        # Save current clipboard content
        original_clipboard = pyperclip.paste()
        
        # Select all text on screen (Ctrl+A)
        pyautogui.hotkey('ctrl', 'a')
        time.sleep(1)
        
        # Copy selected text (Ctrl+C)
        pyautogui.hotkey('ctrl', 'c')
        time.sleep(1)
        
        # Get text from clipboard
        copied_text = pyperclip.paste()
        
        # Restore original clipboard content
        pyperclip.copy(original_clipboard)
        
        if copied_text and copied_text.strip():
            return f"📖 Screen se text padh raha hoon:\n\n{copied_text}"
        else:
            return "❌ Screen par koi selectable text nahi mila. Koi document, webpage ya text editor khol ke try karein."
            
    except Exception as e:
        return f"❌ Text read karne mein error: {str(e)}"