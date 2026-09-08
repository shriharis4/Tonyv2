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


import base64
import cv2
import os
import json
import aiohttp
import asyncio
from typing import Optional
from dataclasses import dataclass

@dataclass
class CameraConfig:
    """Camera configuration settings"""
    width: int = 1920
    height: int = 1080
    warmup_frames: int = 15
    jpeg_quality: int = 95
    timeout: int = 30


class GeminiImageAnalyzer:
    """Analyze images using Google Gemini API"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError("Google API key is required. Set GOOGLE_API_KEY environment variable.")
        
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models"
        self.model = "gemini-2.0-flash"
        self.camera_config = CameraConfig()
        
    async def capture_image(self) -> Optional[bytes]:
        """Capture high-quality image from webcam"""
        try:
            cap = cv2.VideoCapture(0)
            if not cap.isOpened():
                print("⚠️ Camera not available")
                return None
            
            # Set camera resolution
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.camera_config.width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.camera_config.height)
            
            # Warmup for better exposure/focus
            for _ in range(self.camera_config.warmup_frames):
                cap.read()
            
            # Capture frame
            ret, frame = cap.read()
            cap.release()
            
            if not ret:
                print("⚠️ Failed to capture photo")
                return None
            
            # Encode as JPEG
            encode_params = [cv2.IMWRITE_JPEG_QUALITY, self.camera_config.jpeg_quality]
            success, encoded_image = cv2.imencode('.jpg', frame, encode_params)
            
            if success:
                return encoded_image.tobytes()
            return None
            
        except Exception as e:
            print(f"❌ Camera error: {e}")
            return None
    
    async def analyze_image(self, query: str, image_bytes: bytes) -> str:
        """Send image and query to Gemini API for analysis"""
        try:
            # Encode image to base64
            image_base64 = base64.b64encode(image_bytes).decode('utf-8')
            
            # Prepare the request payload
            payload = {
                "contents": [{
                    "parts": [
                        {"text": query},
                        {
                            "inline_data": {
                                "mime_type": "image/jpeg",
                                "data": image_base64
                            }
                        }
                    ]
                }],
                "generationConfig": {
                    "temperature": 0.4,
                    "topP": 0.95,
                    "maxOutputTokens": 2048,
                }
            }
            
            headers = {
                "Content-Type": "application/json",
                "x-goog-api-key": self.api_key
            }
            
            url = f"{self.base_url}/{self.model}:generateContent"
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.camera_config.timeout)) as session:
                async with session.post(url, json=payload, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        # Extract response text
                        if "candidates" in data and len(data["candidates"]) > 0:
                            candidate = data["candidates"][0]
                            if "content" in candidate and "parts" in candidate["content"]:
                                parts = candidate["content"]["parts"]
                                if len(parts) > 0 and "text" in parts[0]:
                                    return parts[0]["text"]
                        
                        return "No valid response from AI"
                    
                    else:
                        error_text = await response.text()
                        return f"API Error ({response.status}): {error_text}"
                        
        except aiohttp.ClientError as e:
            return f"Network error: {str(e)}"
        except Exception as e:
            return f"Analysis error: {str(e)}"
    
    async def quick_analyze(self, query: str) -> str:
        """Complete pipeline: capture and analyze"""
        try:
            print("📸 Capturing image...")
            image_bytes = await self.capture_image()
            
            if not image_bytes:
                return "Failed to capture image. Please check your camera."
            
            print("🤖 Analyzing with Gemini AI...")
            result = await self.analyze_image(query, image_bytes)
            
            return result
            
        except Exception as e:
            return f"Analysis failed: {str(e)}"


# Decorator for LiveKit integration
from livekit.agents import function_tool

@function_tool()
async def camera_analysis(query: str) -> str:
    """
    Takes a high-quality photo, saves it, and analyzes using Google Gemini AI
    """
    try:
        # Initialize analyzer
        analyzer = GeminiImageAnalyzer()
        
        # Translate query if needed (using your existing translation function)
        if not is_english(query):
            translated_query = await translate_to_english_free(query)
            if translated_query:
                query = translated_query
        
        # Perform analysis
        result = await analyzer.quick_analyze(query)
        
        return result
        
    except ValueError as e:
        return f"Configuration error: {str(e)}. Please set GOOGLE_API_KEY environment variable."
    except Exception as e:
        return f"Error: {str(e)}"

