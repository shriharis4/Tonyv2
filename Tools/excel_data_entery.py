import pandas as pd
import os
import pyautogui
import time
import asyncio
import aiohttp
import json
from livekit.agents import function_tool

# Global variables
current_excel_file = None

# ========== TRANSLATION FUNCTIONS (Internal) ==========

async def translate_to_english_free(text: str) -> str:
    """
    Translate text to English using free APIs without API keys
    """
    if not text.strip():
        return text
    
    # Check if text is already in English
    if is_english(text):
        return text
    
    # Try multiple free translation services
    translation = await try_google_translate(text)
    if translation:
        return translation
    
    translation = await try_my_memory_translate(text)
    if translation:
        return translation
    
    # Fallback to basic translation if all APIs fail
    return fallback_translation(text)

def is_english(text: str) -> bool:
    """Check if text is already in English"""
    try:
        return all(ord(char) < 128 or char.isspace() for char in text)
    except:
        return True

async def try_google_translate(text: str) -> str:
    """
    Try Google Translate (free unofficial API)
    """
    try:
        url = "https://translate.googleapis.com/translate_a/single"
        params = {
            'client': 'gtx',
            'sl': 'auto',
            'tl': 'en',
            'dt': 't',
            'q': text
        }
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if data and len(data) > 0:
                        translated_parts = [part[0] for part in data[0] if part[0]]
                        return ''.join(translated_parts)
    except:
        return None

async def try_my_memory_translate(text: str) -> str:
    """
    Try MyMemory Translation API (free)
    """
    try:
        url = "https://api.mymemory.translated.net/get"
        params = {
            'q': text,
            'langpair': 'auto|en'
        }
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('responseStatus') == 200:
                        return data['responseData']['translatedText']
    except:
        return None

def fallback_translation(text: str) -> str:
    """
    Basic fallback translation for common words
    """
    basic_translations = {
        # Hindi to English
        "नाम": "Name", "उम्र": "Age", "शहर": "City", "देश": "Country",
        "विभाग": "Department", "वेतन": "Salary", "पता": "Address",
        "मोबाइल": "Mobile", "ईमेल": "Email", "जन्मतिथि": "Birthdate",
        "आईटी": "IT", "एचआर": "HR", "वित्त": "Finance", "बिक्री": "Sales",
        "मार्केटिंग": "Marketing", "उत्पादन": "Production",
        
        # Common Indian names
        "राज": "Raj", "प्रिया": "Priya", "अमित": "Amit", "नीतू": "Neetu",
        "सोनू": "Sonu", "मोना": "Mona", "रवि": "Ravi", "सीमा": "Seema",
        
        # Cities
        "मुंबई": "Mumbai", "दिल्ली": "Delhi", "बेंगलुरु": "Bangalore",
        "चेन्नई": "Chennai", "कोलकाता": "Kolkata", "पुणे": "Pune",
        "हैदराबाद": "Hyderabad", "अहमदाबाद": "Ahmedabad",
        
        # Basic words
        "हाँ": "Yes", "नहीं": "No", "ठीक": "OK", "अच्छा": "Good"
    }
    
    words = text.split()
    translated_words = []
    
    for word in words:
        clean_word = word.strip('.,!?;:')
        if clean_word in basic_translations:
            translated_words.append(basic_translations[clean_word])
        else:
            translated_words.append(word)
    
    return ' '.join(translated_words)

# ========== EXCEL OPERATIONS ==========
    
@function_tool()
async def create_excel_file(file_name: str) -> str:
    """
    Creates a new Excel file in OneDrive Documents folder and opens it.
    """
    global current_excel_file
    
    try:
        onedrive_path = os.path.join(os.path.expanduser("~"), "OneDrive")
        documents_folder = os.path.join(onedrive_path, "Documents")
        
        if not file_name.endswith('.xlsx'):
            file_name += '.xlsx'

        file_path = os.path.join(documents_folder, file_name)
        df = pd.DataFrame()
        df.to_excel(file_path, index=False)
        current_excel_file = file_path
        
        os.startfile(file_path)
        time.sleep(3)
        
        return f"Excel file '{file_name}' created and opened successfully."
        
    except Exception as e:
        return f"Error creating Excel file: {str(e)}"

@function_tool()
async def enter_data_quick(data: str) -> str:
    """
    Quick data entry - automatically types and moves down.
    Works with any active Excel file.
    """
    try:
        print(f"DEBUG: Typing data: {data}")
        
        # Translate data
        translated_data = await translate_to_english_free(data)
        print(f"DEBUG: Translated data: {translated_data}")
        
        # Ensure Excel is active
        try:
            pyautogui.click(100, 100)
            time.sleep(0.5)
        except:
            print("DEBUG: Could not click, continuing...")
        
        # Type data
        pyautogui.write(translated_data, interval=0.1)
        time.sleep(0.5)
        
        # Move down
        pyautogui.press('enter')
        time.sleep(0.3)
        
        # Save
        pyautogui.hotkey('ctrl', 's')
        time.sleep(0.3)
        
        print(f"DEBUG: Data typed successfully: {translated_data}")
        return f"✅ '{translated_data}' enter ho gaya aur niche move kar diya"
        
    except Exception as e:
        print(f"DEBUG: Error in enter_data_quick: {str(e)}")
        return f"❌ Error: {str(e)}. Please make sure Excel window is active."

@function_tool()
async def enter_multiple_data_quick(data_sequence: str) -> str:
    """
    Quick multiple data entry - types multiple values in separate cells downwards.
    Works with any active Excel file (manually opened or tool-created).
    """
    try:
        print(f"DEBUG: Typing multiple data downwards: {data_sequence}")
        
        # Multiple separators ko handle karo - comma, newline, aur space
        # Pehle newlines ko comma mein convert karo
        data_sequence = data_sequence.replace('\n', ',').replace('\\n', ',')
        
        # Ab comma se split karo
        data_list = []
        for item in data_sequence.split(','):
            item = item.strip()
            if item:  # Empty strings ko ignore karo
                data_list.append(item)
        
        print(f"DEBUG: Parsed data list: {data_list}")
        
        translated_data = []
        
        for data in data_list:
            translated_data.append(await translate_to_english_free(data))
        
        print(f"DEBUG: Translated multiple data: {translated_data}")
        
        # Ensure Excel is active
        try:
            pyautogui.click(100, 100)
            time.sleep(1)
        except:
            print("DEBUG: Could not click at default position, continuing...")
        
        # Agar koi data nahi hai
        if not translated_data:
            return "❌ Koi valid data nahi mila"
        
        # Type first data directly
        pyautogui.write(translated_data[0], interval=0.1)
        time.sleep(0.5)
        
        # For remaining data
        for i in range(1, len(translated_data)):
            # Press Down arrow to move to next cell
            pyautogui.press('down')
            time.sleep(0.3)
            
            # Type data directly
            pyautogui.write(translated_data[i], interval=0.1)
            time.sleep(0.5)
        
        # Save
        pyautogui.hotkey('ctrl', 's')
        time.sleep(0.5)
        
        return f"✅ {len(translated_data)} values alag alag cells mein niche enter ho gaye"
         
    except Exception as e:
        print(f"DEBUG: Error in enter_multiple_data_quick: {str(e)}")
        return f"❌ Error: {str(e)}. Please make sure Excel window is active and try again."
    
@function_tool()
async def save_excel_changes() -> str:
    """
    Saves the Excel file using Ctrl+S.
    """
    try:
        pyautogui.hotkey('ctrl', 's')
        return "💾 File saved successfully"
    except Exception as e:
        return f"❌ Error saving file: {str(e)}"

# ========== MOVEMENT FUNCTIONS ==========

@function_tool()
async def move_left() -> str:
    """
    Moves one cell left using Left arrow key.
    """
    try:
        pyautogui.press('left')
        return "⬅️ Moved left one cell"
    except Exception as e:
        return f"❌ Error moving left: {str(e)}"

@function_tool()
async def move_right() -> str:
    """
    Moves one cell right using Right arrow key.
    """
    try:
        pyautogui.press('right')
        return "➡️ Moved right one cell"
    except Exception as e:
        return f"❌ Error moving right: {str(e)}"

@function_tool()
async def move_up() -> str:
    """
    Moves one cell up using Up arrow key.
    """
    try:
        pyautogui.press('up')
        return "⬆️ Moved up one cell"
    except Exception as e:
        return f"❌ Error moving up: {str(e)}"

@function_tool()
async def move_down() -> str:
    """
    Moves one cell down using Down arrow key.
    """
    try:
        pyautogui.press('down')
        return "⬇️ Moved down one cell"
    except Exception as e:
        return f"❌ Error moving down: {str(e)}"
    
@function_tool()
async def go_to_cell(cell_address: str) -> str:
    """
    Moves cursor to a specific cell in Excel using Ctrl+G (Go To).
    
    Args:
        cell_address: Excel cell address like "A1", "B5", "C10"
    
    Returns:
        str: Confirmation message
    """
    try:
        # Ensure Excel is active
        pyautogui.click(100, 100)
        time.sleep(0.5)
        
        # Press Ctrl+G (Go To shortcut in Excel)
        pyautogui.hotkey('ctrl', 'g')
        time.sleep(0.5)
        
        # Type the cell address
        pyautogui.write(cell_address)
        time.sleep(0.3)
        
        # Press Enter to go to the cell
        pyautogui.press('enter')
        time.sleep(0.5)
        
        return f"✅ Cursor moved to cell {cell_address}"
        
    except Exception as e:
        return f"❌ Error going to cell: {str(e)}"

# ========== DATA MANIPULATION ==========

@function_tool()
async def delete_all_data() -> str:
    """
    Selects all data in current cell and deletes it completely.
    """
    try:
        pyautogui.hotkey('ctrl', 'a')
        pyautogui.press('delete')
        return "✅ Current cell data completely deleted"
    except Exception as e:
        return f"❌ Error deleting cell data: {str(e)}"

@function_tool()
async def delete_current_cell() -> str:
    """
    Deletes data from current cell with single delete press (without selecting).
    """
    try:
        pyautogui.press('delete')
        return "✅ Current cell data deleted"
    except Exception as e:
        return f"❌ Error deleting cell: {str(e)}"
    
@function_tool()
async def toggle_text_bold(bold_option: str = "bold") -> str:
    """
    Make text bold or unbold in Excel.
    
    Args:
        bold_option: "bold" (text ko bold kare) ya "unbold" (text ko normal kare)
                     Default: "bold"
    
    Returns:
        str: Confirmation message
    """
    try:
        print(f"DEBUG: Toggling text bold: {bold_option}")
        
        # Excel window activate करने की कोशिश
        try:
            pyautogui.click(100, 100)
            time.sleep(0.5)
        except:
            print("DEBUG: Could not click, continuing...")
        
        # Bold/unbold करने के लिए Ctrl+B shortcut use करें
        if bold_option.lower() == "bold":
            # Bold करने के लिए Ctrl+B
            pyautogui.hotkey('ctrl', 'b')
            time.sleep(0.3)
            action = "bold"
        elif bold_option.lower() == "unbold":
            # Unbold करने के लिए भी Ctrl+B (toggle hota hai)
            pyautogui.hotkey('ctrl', 'b')
            time.sleep(0.3)
            action = "unbold"
        else:
            # Agar option samajh nahi aaya तो toggle करें
            pyautogui.hotkey('ctrl', 'b')
            time.sleep(0.3)
            action = "toggled"
        
        # Save changes
        pyautogui.hotkey('ctrl', 's')
        time.sleep(0.3)
        
        return f"✅ Text {action} kar diya gaya hai"
        
    except Exception as e:
        print(f"DEBUG: Error in toggle_text_bold: {str(e)}")
        return f"❌ Error: {str(e)}. Please ensure Excel is active."
    
@function_tool()
async def select_row_or_column(select_type: str) -> str:
    """
    Selects entire row or entire column in Excel (not just data range).
    Excel में पूरी row या पूरी column select करता है।
    
    Args:
        select_type: "row" (पूरी row select करे) या "column" (पूरी column select करे)
    """
    try:
        print(f"DEBUG: Selecting entire {select_type}...")
        
        # Activate Excel window
        try:
            pyautogui.click(100, 100)
            time.sleep(0.2)
        except:
            print("DEBUG: Could not click, but continuing...")
        
        # Clear any existing selection
        pyautogui.press('esc')
        time.sleep(0.1)
        
        # Convert to lowercase
        select_type = select_type.lower().strip()
        
        # Determine what to select
        if select_type in ["row", "रो", "पंक्ति", "लाइन"]:
            # Select ENTIRE row using Shift+Space
            print("DEBUG: Selecting entire row")
            pyautogui.hotkey('shift', 'space')
            time.sleep(0.2)
            
            return "✅ पूरी row select हो गयी है।"
            
        elif select_type in ["column", "कॉलम", "स्तंभ", "खंड"]:
            # Select ENTIRE column using Ctrl+Space
            print("DEBUG: Selecting entire column")
            pyautogui.hotkey('ctrl', 'space')
            time.sleep(0.2)
            
            return "✅ पूरी column select हो गयी है।"
            
        else:
            # Smart detection for Hindi/English mixed input
            if any(word in select_type for word in ["row", "रो", "पंक्ति"]):
                return await select_row_or_column("row")
            elif any(word in select_type for word in ["column", "कॉलम", "स्तंभ"]):
                return await select_row_or_column("column")
            else:
                return "❌ कृपया स्पष्ट बताएँ: 'row' या 'column'"
            
    except Exception as e:
        print(f"DEBUG: Error in select_row_or_column: {str(e)}")
        return f"❌ Error: {str(e)}"
    
@function_tool()
async def sort_excel_data(sort_direction: str) -> str:
    """
    Sort column using Down arrow to select second option in warning dialog.
    """
    try:
        print(f"DEBUG: Sorting with down arrow method: {sort_direction}")
        
        # Activate Excel
        pyautogui.click(100, 100)
        time.sleep(0.3)
        
        # Clear and select ONLY current column
        pyautogui.press('esc')
        time.sleep(0.1)
        
        # Select column using Ctrl+Space (entire column)
        pyautogui.hotkey('ctrl', 'space')
        time.sleep(0.3)
        
        # Determine sort direction
        is_descending = any(word in sort_direction.lower() for word in 
                           ["desc", "z to a", "बड़े", "अवरोही", "descending", "large"])
        
        # Apply sort shortcut
        if is_descending:
            pyautogui.hotkey('alt', 'a', 's', 'd')  # Sort Z to A
            result_msg = "descending (बड़े से छोटे)"
        else:
            pyautogui.hotkey('alt', 'a', 's', 'a')  # Sort A to Z
            result_msg = "ascending (छोटे से बड़े)"
        
        # Wait for dialog - IMPORTANT: Give enough time
        time.sleep(2.0)  # 2 seconds wait
        
        # **NEW METHOD: Use DOWN ARROW to select second option**
        # Press DOWN arrow key to move to "Continue with current selection"
        pyautogui.press('down')
        time.sleep(0.3)
        
        # Press ENTER to confirm
        pyautogui.press('enter')
        time.sleep(0.5)
        
        # Clear selection
        pyautogui.press('esc')
        time.sleep(0.1)
        
        # Save
        pyautogui.hotkey('ctrl', 's')
        time.sleep(0.2)
        
        return f"✅ Column {result_msg} में sort हो गया।"
        
    except Exception as e:
        print(f"DEBUG: Error: {str(e)}")
        return f"❌ Error: {str(e)}"
    
@function_tool()
async def excel_clipboard_action(action: str) -> str:
    """
    Perform cut, copy, paste, or delete action in Excel.
    
    Args:
        action: "cut", "copy", "paste", या "delete"
    """
    try:
        # Activate Excel
        pyautogui.click(100, 100)
        time.sleep(0.2)
        
        action = action.lower().strip()
        
        if action in ["cut", "कट", "काटो", "कट करो"]:
            pyautogui.hotkey('ctrl', 'x')
            return "✅ Data cut ho gaya. Ab paste karne ke liye cell select karo aur 'paste' bolo."
            
        elif action in ["copy", "कॉपी", "नकल", "कॉपी करो"]:
            pyautogui.hotkey('ctrl', 'c')
            return "✅ Data copy ho gaya. Ab paste karne ke liye cell select karo aur 'paste' bolo."
            
        elif action in ["paste", "पेस्ट", "चिपकाओ", "पेस्ट करो"]:
            pyautogui.hotkey('ctrl', 'v')
            return "✅ Data paste ho gaya."
            
        elif action in ["delete", "डिलीट", "हटाओ", "मिटाओ", "डिलीट करो"]:
            # Delete selected data
            pyautogui.press('delete')
            time.sleep(0.2)
            return "✅ Selected data delete ho gaya."
            
        else:
            return "❌ कृपया 'cut', 'copy', 'paste', या 'delete' बताएँ।"
        
    except Exception as e:
        return f"❌ Error: {str(e)}"  
    
@function_tool()
async def calculate_sum(target_cell: str = "below") -> str:
    """
    Better sum calculation using Python to calculate.
    """
    try:
        print(f"DEBUG: Smart sum calculation to: {target_cell}")
        
        # Activate Excel
        pyautogui.click(100, 100)
        time.sleep(0.2)
        
        # Step 1: Copy the selected data
        pyautogui.hotkey('ctrl', 'c')
        time.sleep(0.3)
        
        # Step 2: Get clipboard data and calculate sum in Python
        import pyperclip
        
        # Get clipboard content
        clipboard_data = pyperclip.paste()
        print(f"DEBUG: Clipboard data: {clipboard_data}")
        
        # Parse and calculate sum
        numbers = []
        lines = clipboard_data.split('\n')
        
        for line in lines:
            cells = line.split('\t')
            for cell in cells:
                cell = cell.strip()
                if cell:
                    # Try to convert to number
                    try:
                        # Remove any commas, currency symbols, etc.
                        clean_cell = cell.replace(',', '').replace('₹', '').replace('$', '').strip()
                        num = float(clean_cell)
                        numbers.append(num)
                    except:
                        # Not a number, skip
                        pass
        
        if not numbers:
            return "❌ कोई numbers नहीं मिले। कृपया numbers select करें।"
        
        total = sum(numbers)
        print(f"DEBUG: Calculated sum: {total} from {len(numbers)} numbers")
        
        # Step 3: Write the sum to desired location
        target_cell = target_cell.lower()
        
        if target_cell == "below":
            # Go below the selection
            pyautogui.hotkey('ctrl', 'down')
            time.sleep(0.1)
            pyautogui.press('down')
            time.sleep(0.1)
            
        elif target_cell == "right":
            # Go right of the selection
            pyautogui.hotkey('ctrl', 'right')
            time.sleep(0.1)
            pyautogui.press('right')
            time.sleep(0.1)
            
        elif len(target_cell) <= 3 and target_cell[0].isalpha():
            # Specific cell
            pyautogui.hotkey('ctrl', 'g')
            time.sleep(0.3)
            pyautogui.write(target_cell.upper())
            pyautogui.press('enter')
            time.sleep(0.3)
            
        else:
            # Default: below
            pyautogui.hotkey('ctrl', 'down')
            time.sleep(0.1)
            pyautogui.press('down')
            time.sleep(0.1)
        
        # Write the sum
        pyautogui.write(str(total))
        time.sleep(0.2)
        
        # Save
        pyautogui.hotkey('ctrl', 's')
        
        return f"✅ Sum calculate हो गया: {total}"
        
    except ImportError:
        # If pyperclip not available, use fallback method
        print("DEBUG: pyperclip not available, using fallback")
        return await calculate_sum_fallback(target_cell)
    except Exception as e:
        print(f"DEBUG: Error: {str(e)}")
        return f"❌ Error: {str(e)}"

async def calculate_sum_fallback(target_cell: str) -> str:
    """
    Fallback method without pyperclip.
    """
    try:
        # Simple AutoSum method
        pyautogui.click(100, 100)
        time.sleep(0.2)
        
        # AutoSum
        pyautogui.hotkey('alt', '=')
        time.sleep(0.3)
        pyautogui.press('enter')
        
        # Convert to value
        pyautogui.hotkey('ctrl', 'c')
        time.sleep(0.1)
        pyautogui.hotkey('alt', 'h', 'v', 'v')  # Paste Values
        time.sleep(0.3)
        pyautogui.press('enter')
        
        # Save
        pyautogui.hotkey('ctrl', 's')
        
        return "✅ Sum calculate हो गया (fallback method से)"
        
    except Exception as e:
        return f"❌ Error: {str(e)}"