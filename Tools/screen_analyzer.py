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


import pyautogui
import base64
import json
import aiohttp
import asyncio
import os
import tempfile
from datetime import datetime
from typing import Optional, Tuple
from dataclasses import dataclass
from livekit.agents import function_tool



@dataclass
class ScreenConfig:
    """Screen capture configuration"""
    region: Optional[Tuple[int, int, int, int]] = None  # (x, y, width, height)
    scale_factor: float = 1.0
    jpeg_quality: int = 90
    timeout: int = 30


class GeminiScreenAnalyzer:
    """Analyze screen content using Google Gemini API"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError("Google API key is required. Set GOOGLE_API_KEY environment variable.")
        
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models"
        self.model = "gemini-2.0-flash"  # Good for vision tasks
        self.screen_config = ScreenConfig()
        
    async def capture_screenshot(self) -> Optional[bytes]:
        """Capture screenshot of the entire screen or specific region"""
        try:
            # Get screen dimensions
            screen_width, screen_height = pyautogui.size()
            
            # Determine capture region
            if self.screen_config.region:
                x, y, width, height = self.screen_config.region
                # Validate region
                if (x + width <= screen_width and y + height <= screen_height and 
                    width > 0 and height > 0):
                    region = (x, y, width, height)
                else:
                    print("⚠️ Invalid region specified, capturing full screen")
                    region = None
            else:
                region = None
            
            # Capture screenshot
            if region:
                screenshot = pyautogui.screenshot(region=region)
            else:
                screenshot = pyautogui.screenshot()
            
            # Convert to JPEG bytes
            import io
            from PIL import Image
            
            # Resize if scale factor is not 1.0
            if self.screen_config.scale_factor != 1.0:
                new_width = int(screenshot.width * self.screen_config.scale_factor)
                new_height = int(screenshot.height * self.screen_config.scale_factor)
                screenshot = screenshot.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            # Save to bytes
            img_byte_arr = io.BytesIO()
            screenshot.save(img_byte_arr, format='JPEG', 
                          quality=self.screen_config.jpeg_quality,
                          optimize=True)
            img_byte_arr.seek(0)
            
            # Add timestamp overlay (optional)
            timestamped_bytes = await self._add_timestamp(img_byte_arr.getvalue())
            
            # Save local copy for debugging (optional)
            if os.getenv("DEBUG_SCREENSHOTS"):
                debug_dir = "screenshots_debug"
                os.makedirs(debug_dir, exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                debug_path = os.path.join(debug_dir, f"screenshot_{timestamp}.jpg")
                with open(debug_path, "wb") as f:
                    f.write(timestamped_bytes)
                print(f"📁 Screenshot saved: {debug_path}")
            
            return timestamped_bytes
            
        except Exception as e:
            print(f"❌ Screenshot capture error: {e}")
            return None
    
    async def _add_timestamp(self, image_bytes: bytes) -> bytes:
        """Add timestamp overlay to screenshot"""
        try:
            from PIL import Image, ImageDraw, ImageFont
            import io
            
            # Open image
            image = Image.open(io.BytesIO(image_bytes))
            
            # Add timestamp text
            draw = ImageDraw.Draw(image)
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Try to use a font
            try:
                font = ImageFont.truetype("arial.ttf", 20)
            except:
                font = ImageFont.load_default()
            
            # Calculate text position (bottom right)
            text_bbox = draw.textbbox((0, 0), timestamp, font=font)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]
            margin = 10
            
            position = (
                image.width - text_width - margin,
                image.height - text_height - margin
            )
            
            # Draw background rectangle
            bg_bbox = (
                position[0] - 5,
                position[1] - 2,
                position[0] + text_width + 5,
                position[1] + text_height + 2
            )
            draw.rectangle(bg_bbox, fill=(0, 0, 0, 180))
            
            # Draw timestamp text
            draw.text(position, timestamp, fill=(255, 255, 255), font=font)
            
            # Save back to bytes
            output_bytes = io.BytesIO()
            image.save(output_bytes, format='JPEG', 
                      quality=self.screen_config.jpeg_quality)
            output_bytes.seek(0)
            
            return output_bytes.getvalue()
            
        except Exception as e:
            print(f"⚠️ Timestamp overlay failed: {e}")
            return image_bytes  # Return original if timestamp fails
    
    async def analyze_screen(self, query: str, screenshot_bytes: bytes) -> str:
        """Send screenshot and query to Gemini API for analysis"""
        try:
            # Encode screenshot to base64
            image_base64 = base64.b64encode(screenshot_bytes).decode('utf-8')
            
            # Prepare the request payload with enhanced context
            enhanced_query = f"""
            Analyze this screenshot of the computer screen and answer the following question:
            
            Question: {query}
            
            Please provide a detailed analysis including:
            1. What applications/windows are visible
            2. What text/content is displayed
            3. The overall context/purpose of what's shown
            4. Any specific details requested in the question
            
            If you cannot see clearly or something is not visible, please mention that.
            """
            
            payload = {
                "contents": [{
                    "parts": [
                        {"text": enhanced_query},
                        {
                            "inline_data": {
                                "mime_type": "image/jpeg",
                                "data": image_base64
                            }
                        }
                    ]
                }],
                "generationConfig": {
                    "temperature": 0.2,  # Lower for more factual analysis
                    "topP": 0.9,
                    "maxOutputTokens": 4096,  # More tokens for detailed analysis
                    "topK": 40
                },
                "safetySettings": [
                    {
                        "category": "HARM_CATEGORY_HARASSMENT",
                        "threshold": "BLOCK_NONE"
                    },
                    {
                        "category": "HARM_CATEGORY_HATE_SPEECH",
                        "threshold": "BLOCK_NONE"
                    },
                    {
                        "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                        "threshold": "BLOCK_NONE"
                    },
                    {
                        "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                        "threshold": "BLOCK_NONE"
                    }
                ]
            }
            
            headers = {
                "Content-Type": "application/json",
                "x-goog-api-key": self.api_key
            }
            
            url = f"{self.base_url}/{self.model}:generateContent"
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.screen_config.timeout)) as session:
                async with session.post(url, json=payload, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        # Extract response text
                        if "candidates" in data and len(data["candidates"]) > 0:
                            candidate = data["candidates"][0]
                            if "content" in candidate and "parts" in candidate["content"]:
                                parts = candidate["content"]["parts"]
                                if len(parts) > 0 and "text" in parts[0]:
                                    response_text = parts[0]["text"]
                                    # Clean up response
                                    response_text = response_text.strip()
                                    return response_text
                        
                        return "Could not analyze the screen content."
                    
                    else:
                        error_text = await response.text()
                        return f"API Error ({response.status}): {error_text}"
                        
        except aiohttp.ClientError as e:
            return f"Network error: {str(e)}"
        except Exception as e:
            return f"Analysis error: {str(e)}"
    
    async def quick_screen_analysis(self, query: str) -> str:
        """Complete pipeline: capture screenshot and analyze"""
        try:
            print("📱 Capturing screenshot...")
            screenshot_bytes = await self.capture_screenshot()
            
            if not screenshot_bytes:
                return "Failed to capture screenshot. Please check your screen settings."
            
            print(f"📊 Screenshot captured ({len(screenshot_bytes):,} bytes)")
            print("🤖 Analyzing screen content with Gemini AI...")
            
            # Translate query if needed
            
            
            if not is_english(query):
                translated_query = await translate_to_english_free(query)
                if translated_query:
                    query = translated_query
                    print(f"🔤 Translated query: {query}")
            
            result = await self.analyze_screen(query, screenshot_bytes)
            
            return result
            
        except Exception as e:
            return f"Screen analysis failed: {str(e)}"
    
    def set_region(self, x: int, y: int, width: int, height: int):
        """Set specific screen region to capture"""
        self.screen_config.region = (x, y, width, height)
    
    def clear_region(self):
        """Clear region setting to capture full screen"""
        self.screen_config.region = None
    
    def set_scale(self, scale_factor: float):
        """Set scaling factor for screenshot (0.1 to 2.0)"""
        self.screen_config.scale_factor = max(0.1, min(2.0, scale_factor))


# Main function tool for LiveKit integration
@function_tool()
async def analyze_screen(query: str = "What's visible on my screen?") -> str:
    """
    Takes a screenshot of the current screen and analyzes it using Google Gemini AI.
    Can answer questions about what's displayed, read text, identify applications, etc.
    
    Args:
        query: What you want to know about the screen content. Examples:
            - "What's visible on my screen?"
            - "Read the text in the browser window"
            - "What application is open on the right side?"
            - "Is there any error message showing?"
            - "Describe everything you see"
    """
    try:
        # Initialize analyzer
        analyzer = GeminiScreenAnalyzer()
        
        # Perform analysis
        result = await analyzer.quick_screen_analysis(query)
        
        return result
        
    except ValueError as e:
        return f"Configuration error: {str(e)}. Please set GOOGLE_API_KEY environment variable."
    except Exception as e:
        return f"Error analyzing screen: {str(e)}"

