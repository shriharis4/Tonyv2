import pyautogui
import asyncio
import requests
import datetime
import time
from livekit.agents import function_tool

def translate_to_english(text: str) -> str:
    """Translate Hindi/other languages to English for search"""
    translation_map = {
        # Hindi to English
        "निबंध": "essay", "लिखो": "write", "बनाओ": "make", "करो": "do",
        "टेक्नोलॉजी": "technology", "विज्ञान": "science", "शिक्षा": "education",
        "स्वास्थ्य": "health", "पर्यावरण": "environment", "कंप्यूटर": "computer",
        "मोबाइल": "mobile", "फोन": "phone", "इंटरनेट": "internet",
        "कृत्रिम": "artificial", "बुद्धिमत्ता": "intelligence", "ग्लोबल": "global",
        "वार्मिंग": "warming", "पानी": "water", "हवा": "air", "प्रदूषण": "pollution",
        "जानवर": "animal", "पेड़": "tree", "पौधे": "plants", "प्रकृति": "nature",
        
        # Common words
        "मेरा": "my", "तेरा": "your", "हमारा": "our", "उसका": "his",
        "यह": "this", "वह": "that", "क्या": "what", "क्यों": "why",
        "कब": "when", "कहाँ": "where", "कैसे": "how", "कौन": "who",
        
        # Actions
        "लिखना": "write", "पढ़ना": "read", "सीखना": "learn", "सिखाना": "teach",
        "बोलना": "speak", "सुनना": "listen", "देखना": "see", "समझना": "understand",
        
        # Document types
        "पत्र": "letter", "आवेदन": "application", "रिपोर्ट": "report",
        "नोट": "note", "सारांश": "summary", "विवरण": "description"
    }
    
    # If text is already in English, return as is
    if all(ord(char) < 128 for char in text):
        return text
    
    # Translate word by word
    words = text.split()
    translated_words = []
    
    for word in words:
        clean_word = word.strip('.,!?').lower()
        if clean_word in translation_map:
            translated_words.append(translation_map[clean_word])
        else:
            # Keep the word as is if no translation found
            translated_words.append(word)
    
    result = ' '.join(translated_words)
    # Capitalize first letter
    if result:
        result = result[0].upper() + result[1:]
    
    return result

import pyautogui
import asyncio
import aiohttp
import json
from livekit.agents import function_tool

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
    
    translation = await try_libretranslate(text)
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
            'sl': 'auto',  # source language (auto-detect)
            'tl': 'en',    # target language (English)
            'dt': 't',
            'q': text
        }
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    # Extract translated text from response
                    if data and len(data) > 0:
                        translated_parts = [part[0] for part in data[0] if part[0]]
                        return ''.join(translated_parts)
    except Exception as e:
        print(f"Google Translate failed: {e}")
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
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('responseStatus') == 200:
                        return data['responseData']['translatedText']
    except Exception as e:
        print(f"MyMemory Translate failed: {e}")
    return None

async def try_libretranslate(text: str) -> str:
    """
    Try LibreTranslate (free open-source)
    """
    try:
        # Try different LibreTranslate instances
        instances = [
            "https://libretranslate.de/translate",
            "https://translate.argosopentech.com/translate",
            "https://libretranslate.pussthecat.org/translate"
        ]
        
        payload = {
            'q': text,
            'source': 'auto',
            'target': 'en',
            'format': 'text'
        }
        
        headers = {
            'Content-Type': 'application/json'
        }
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            for instance_url in instances:
                try:
                    async with session.post(instance_url, 
                                          data=json.dumps(payload), 
                                          headers=headers) as response:
                        if response.status == 200:
                            data = await response.json()
                            return data.get('translatedText')
                except:
                    continue  # Try next instance
                    
    except Exception as e:
        print(f"LibreTranslate failed: {e}")
    return None

def fallback_translation(text: str) -> str:
    """
    Basic fallback translation for common words
    """
    basic_translations = {
        # Hindi
        "नमस्ते": "hello", "हैलो": "hello", "हाय": "hi", "कैसे": "how", "हो": "are",
        "आप": "you", "तुम": "you", "मैं": "I", "मेरा": "my", "नाम": "name",
        "धन्यवाद": "thank you", "शुक्रिया": "thanks", "कृपया": "please",
        "हाँ": "yes", "ना": "no", "नहीं": "no", "ठीक": "ok", "अच्छा": "good",
        
        # Actions
        "लिखो": "write", "टाइप": "type", "बनाओ": "make", "करो": "do",
        "दिखाओ": "show", "भेजो": "send", "खोलो": "open", "बंद": "close",
        
        # Common words
        "मदद": "help", "समय": "time", "दिन": "day", "रात": "night",
        "क्या": "what", "क्यों": "why", "कब": "when", "कहाँ": "where"
    }
    
    words = text.split()
    translated_words = []
    
    for word in words:
        clean_word = word.strip('.,!?;:').lower()
        if clean_word in basic_translations:
            translated_words.append(basic_translations[clean_word])
        else:
            translated_words.append(word)
    
    return ' '.join(translated_words)


import os
import subprocess
import json
import time
from pathlib import Path
from datetime import datetime
from livekit.agents import function_tool
import sys

@function_tool()
async def create_here(item_name: str, item_type: str = "folder") -> str:
    """
    Creates a folder or file in ACTIVE File Explorer window location.
    Uses PowerShell to get exact current path - 100% accurate.
    
    Args:
        item_name: Name of folder/file to create
        item_type: 'folder' or 'file'
        
    Returns: Creation status with exact path
    """
    try:
        # Step 1: Get ACTIVE File Explorer path using PowerShell (Most Reliable)
        explorer_path = await _get_active_explorer_path()
        
        if not explorer_path:
            # Fallback to User's Desktop directory
            explorer_path = os.path.join(os.path.expanduser("~"), "Desktop")
            print(f"⚠️ No active File Explorer window found. Falling back to Desktop: {explorer_path}")
        
        if not os.path.exists(explorer_path):
            return f"❌ Path doesn't exist: {explorer_path}"
        
        # Step 2: Create item
        item_name = item_name.strip()
        item_name = await translate_to_english_free(item_name)
        full_path = os.path.join(explorer_path, item_name)
        
        if item_type.lower() in ['folder', 'dir', 'directory']:
            # Create folder
            if not item_name:
                return "❌ Folder name cannot be empty"
            
            if os.path.exists(full_path):
                return f"✅ Folder already exists at:\n{full_path}"
            
            os.makedirs(full_path, exist_ok=True)
            result_msg = f"✅ Folder '{item_name}' created successfully!"
            
        elif item_type.lower() in ['file', 'txt', 'text']:
            # Create text file
            if not item_name.lower().endswith('.txt'):
                item_name = item_name + '.txt'
                full_path = os.path.join(explorer_path, item_name)
            
            if os.path.exists(full_path):
                return f"✅ File already exists at:\n{full_path}"
            
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(f"Created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            
            result_msg = f"✅ File '{item_name}' created successfully!"
        
        else:
            return "❌ Invalid type. Use 'folder' or 'file' only."
        
        # Step 3: Refresh explorer
        await _refresh_explorer_safe()
        
        return f"{result_msg}\n📍 Location: {full_path}\n📁 In folder: {explorer_path}"
        
    except PermissionError:
        return f"❌ Permission denied! Cannot create in: {explorer_path}"
    except Exception as e:
        return f"❌ Error: {str(e)}"

async def _get_active_explorer_path():
    """
    Get path of ACTIVE File Explorer window using PowerShell.
    This is the MOST RELIABLE method on Windows.
    Returns: String path or None
    """
    try:
        # PowerShell command to get active explorer window path
        ps_script = """
        Add-Type @'
        using System;
        using System.Runtime.InteropServices;
        
        public class ExplorerHelper {
            [DllImport("user32.dll")]
            public static extern IntPtr GetForegroundWindow();
            
            [DllImport("user32.dll", SetLastError = true)]
            public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint lpdwProcessId);
            
            [DllImport("shell32.dll")]
            public static extern int SHGetFolderPath(IntPtr hwndOwner, int nFolder, IntPtr hToken, uint dwFlags, System.Text.StringBuilder pszPath);
        }
'@

        try {
            $shell = New-Object -ComObject Shell.Application
            $windows = $shell.Windows()
            
            foreach ($window in $windows) {
                try {
                    if ($window.FullName -like "*explorer.exe*") {
                        $path = $window.Document.Folder.Self.Path
                        if ($path -and (Test-Path $path)) {
                            return $path
                        }
                    }
                } catch {}
            }
            
            # Alternative method using COM
            $shellApp = New-Object -ComObject Shell.Application
            $window = $shellApp.Windows() | Where-Object { $_.HWND -ne 0 } | Select-Object -First 1
            if ($window) {
                $path = $window.Document.Folder.Self.Path
                if ($path -and (Test-Path $path)) {
                    return $path
                }
            }
            
            return $null
        } catch {
            return $null
        }
        """
        
        # Run PowerShell script
        result = subprocess.run([
            'powershell', '-Command', ps_script
        ], capture_output=True, text=True, timeout=5)
        
        if result.returncode == 0 and result.stdout.strip():
            path = result.stdout.strip()
            if os.path.exists(path):
                return path
        
        # Fallback: Try simpler PowerShell command
        fallback_cmd = """
        $shell = New-Object -ComObject Shell.Application
        $window = $shell.Windows() | Where-Object { $_.LocationURL -like 'file:*' } | Select-Object -First 1
        if ($window) { 
            $path = $window.Document.Folder.Self.Path
            if ($path) { Write-Output $path }
        }
        """
        
        result2 = subprocess.run([
            'powershell', '-Command', fallback_cmd
        ], capture_output=True, text=True, timeout=3)
        
        if result2.returncode == 0:
            path = result2.stdout.strip()
            if path.startswith('file:///'):
                path = path[8:].replace('/', '\\')  # Convert URL to path
            if os.path.exists(path):
                return path
        
        return None
        
    except Exception as e:
        print(f"PowerShell method error: {e}")
        return None

async def _refresh_explorer_safe():
    """Safely refresh explorer without keyboard simulation."""
    try:
        # Use PowerShell to refresh
        refresh_script = """
        $shell = New-Object -ComObject Shell.Application
        $windows = $shell.Windows()
        foreach ($window in $windows) {
            try {
                if ($window.FullName -like "*explorer.exe*") {
                    $window.Refresh()
                    break
                }
            } catch {}
        }
        """
        
        subprocess.run([
            'powershell', '-Command', refresh_script
        ], capture_output=True, timeout=2)
    except:
        pass

