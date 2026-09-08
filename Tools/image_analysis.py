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


import tkinter as tk
from tkinter import filedialog
import base64
import json
import aiohttp
import asyncio
import os
import mimetypes
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass
from PIL import Image, ImageTk
import io
from livekit.agents import function_tool

@dataclass
class ImageAnalysisConfig:
    """Image analysis configuration"""
    max_image_size_mb: int = 20
    supported_formats: tuple = ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff')
    preview_size: tuple = (300, 300)
    timeout: int = 45


class GeminiImageAnalysis:
    """Analyze local images using Google Gemini API"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError("Google API key is required. Set GOOGLE_API_KEY environment variable.")
        
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models"
        self.model = "gemini-2.0-flash"  # Good for image analysis
        self.config = ImageAnalysisConfig()
        
    def select_image_file(self) -> Optional[str]:
        """
        Open file dialog for user to select an image
        Returns path to selected image or None if cancelled
        """
        try:
            # Initialize Tkinter root window (hidden)
            root = tk.Tk()
            root.withdraw()  # Hide the main window
            root.attributes('-topmost', True)  # Bring to front
            
            # Set up file dialog
            file_path = filedialog.askopenfilename(
                title="Select an image to analyze",
                filetypes=[
                    ("Image files", "*.jpg *.jpeg *.png *.gif *.bmp *.webp *.tiff"),
                    ("JPEG files", "*.jpg *.jpeg"),
                    ("PNG files", "*.png"),
                    ("All files", "*.*")
                ],
                initialdir=str(Path.home() / "Pictures")  # Start in Pictures folder
            )
            
            root.destroy()  # Close Tkinter
            
            if file_path and os.path.exists(file_path):
                return file_path
            return None
            
        except Exception as e:
            print(f"❌ File selection error: {e}")
            return None
    
    def validate_image_file(self, file_path: str) -> Dict[str, Any]:
        """
        Validate the selected image file
        Returns dict with validation status and details
        """
        try:
            # Check file exists
            if not os.path.exists(file_path):
                return {"valid": False, "error": "File does not exist"}
            
            # Check file size
            file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
            if file_size_mb > self.config.max_image_size_mb:
                return {
                    "valid": False, 
                    "error": f"Image too large ({file_size_mb:.1f}MB). Max size: {self.config.max_image_size_mb}MB"
                }
            
            # Check file extension
            file_ext = Path(file_path).suffix.lower()
            if file_ext not in self.config.supported_formats:
                return {
                    "valid": False,
                    "error": f"Unsupported format: {file_ext}. Supported: {', '.join(self.config.supported_formats)}"
                }
            
            # Try to open as image
            try:
                with Image.open(file_path) as img:
                    # Get image info
                    img.verify()  # Verify it's a valid image
                    with Image.open(file_path) as img2:
                        width, height = img2.size
                        
                    return {
                        "valid": True,
                        "path": file_path,
                        "size_mb": file_size_mb,
                        "dimensions": (width, height),
                        "format": img.format,
                        "mode": img.mode if hasattr(img, 'mode') else 'Unknown'
                    }
            except Exception as img_error:
                return {"valid": False, "error": f"Invalid image file: {str(img_error)}"}
                
        except Exception as e:
            return {"valid": False, "error": f"Validation error: {str(e)}"}
    
    def create_image_preview(self, image_path: str) -> Optional[ImageTk.PhotoImage]:
        """
        Create a preview thumbnail of the selected image
        """
        try:
            with Image.open(image_path) as img:
                # Resize for preview
                img.thumbnail(self.config.preview_size, Image.Resampling.LANCZOS)
                
                # Convert to PhotoImage for Tkinter
                photo = ImageTk.PhotoImage(img)
                return photo
                
        except Exception as e:
            print(f"⚠️ Preview creation failed: {e}")
            return None
    
    async def confirm_image_selection(self, image_info: Dict[str, Any]) -> bool:
        """
        Show confirmation dialog with image preview
        Returns True if user confirms, False if cancels
        """
        try:
            # Create Tkinter dialog
            root = tk.Tk()
            root.title("Confirm Image Selection")
            root.attributes('-topmost', True)
            
            # Center the window
            window_width = 400
            window_height = 500
            screen_width = root.winfo_screenwidth()
            screen_height = root.winfo_screenheight()
            center_x = int(screen_width/2 - window_width/2)
            center_y = int(screen_height/2 - window_height/2)
            root.geometry(f'{window_width}x{window_height}+{center_x}+{center_y}')
            
            # Create preview
            preview = self.create_image_preview(image_info["path"])
            
            # Create widgets
            tk.Label(root, text="📷 Selected Image", font=("Arial", 14, "bold")).pack(pady=10)
            
            if preview:
                tk.Label(root, image=preview).pack(pady=10)
            
            # Image details
            details_frame = tk.Frame(root)
            details_frame.pack(pady=10, fill="x", padx=20)
            
            details = [
                f"📄 File: {Path(image_info['path']).name}",
                f"📏 Size: {image_info['dimensions'][0]} × {image_info['dimensions'][1]}",
                f"💾 File Size: {image_info['size_mb']:.2f} MB",
                f"🎨 Format: {image_info.get('format', 'Unknown')}"
            ]
            
            for detail in details:
                tk.Label(details_frame, text=detail, justify="left", anchor="w").pack(fill="x")
            
            # Buttons frame
            button_frame = tk.Frame(root)
            button_frame.pack(pady=20)
            
            confirmed = {"result": False}
            
            def on_confirm():
                confirmed["result"] = True
                root.destroy()
            
            def on_cancel():
                confirmed["result"] = False
                root.destroy()
            
            tk.Button(button_frame, text="✅ Analyze This Image", 
                     command=on_confirm, bg="green", fg="white",
                     padx=20, pady=10).pack(side="left", padx=10)
            
            tk.Button(button_frame, text="❌ Cancel", 
                     command=on_cancel, bg="red", fg="white",
                     padx=20, pady=10).pack(side="right", padx=10)
            
            # Handle window close
            root.protocol("WM_DELETE_WINDOW", on_cancel)
            
            # Run dialog
            root.mainloop()
            
            return confirmed["result"]
            
        except Exception as e:
            print(f"⚠️ Confirmation dialog error: {e}")
            return False
    
    def read_image_file(self, image_path: str) -> Optional[bytes]:
        """
        Read image file and return as bytes
        """
        try:
            with open(image_path, 'rb') as f:
                image_bytes = f.read()
            
            # Optional: Compress large images
            if len(image_bytes) > 5 * 1024 * 1024:  # > 5MB
                image_bytes = self.compress_image(image_bytes)
            
            return image_bytes
            
        except Exception as e:
            print(f"❌ Error reading image: {e}")
            return None
    
    def compress_image(self, image_bytes: bytes, quality: int = 85) -> bytes:
        """
        Compress image to reduce size
        """
        try:
            from PIL import Image
            import io
            
            # Open image from bytes
            img = Image.open(io.BytesIO(image_bytes))
            
            # Convert to RGB if needed
            if img.mode in ('RGBA', 'LA', 'P'):
                bg = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                bg.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = bg
            
            # Save with compression
            output = io.BytesIO()
            img.save(output, format='JPEG', quality=quality, optimize=True)
            
            return output.getvalue()
            
        except Exception as e:
            print(f"⚠️ Compression failed, using original: {e}")
            return image_bytes
    
    async def analyze_image(self, query: str, image_bytes: bytes, mime_type: str = "image/jpeg") -> str:
        """
        Send image and query to Gemini API for analysis
        """
        try:
            # Encode image to base64
            image_base64 = base64.b64encode(image_bytes).decode('utf-8')
            
            # Prepare enhanced query
            enhanced_query = f"""
            Analyze this image in detail and answer the following question:
            
            Question: {query}
            
            Please provide a comprehensive analysis including:
            1. What the image shows (objects, people, scenes, text)
            2. Context and possible meaning
            3. Colors, composition, and visual elements
            4. Any specific details requested
            5. Estimated location or setting if applicable
            6. Emotional tone or mood
            
            Be descriptive and detailed in your analysis.
            """
            
            payload = {
                "contents": [{
                    "parts": [
                        {"text": enhanced_query},
                        {
                            "inline_data": {
                                "mime_type": mime_type,
                                "data": image_base64
                            }
                        }
                    ]
                }],
                "generationConfig": {
                    "temperature": 0.3,
                    "topP": 0.95,
                    "maxOutputTokens": 4096,
                    "topK": 40
                }
            }
            
            headers = {
                "Content-Type": "application/json",
                "x-goog-api-key": self.api_key
            }
            
            url = f"{self.base_url}/{self.model}:generateContent"
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.config.timeout)) as session:
                async with session.post(url, json=payload, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        # Extract response text
                        if "candidates" in data and len(data["candidates"]) > 0:
                            candidate = data["candidates"][0]
                            if "content" in candidate and "parts" in candidate["content"]:
                                parts = candidate["content"]["parts"]
                                if len(parts) > 0 and "text" in parts[0]:
                                    response_text = parts[0]["text"].strip()
                                    return response_text
                        
                        return "Could not analyze the image content."
                    
                    else:
                        error_text = await response.text()
                        return f"API Error ({response.status}): {error_text}"
                        
        except aiohttp.ClientError as e:
            return f"Network error: {str(e)}"
        except Exception as e:
            return f"Analysis error: {str(e)}"
    
    def get_mime_type(self, file_path: str) -> str:
        """
        Get MIME type for the image file
        """
        mime_type, _ = mimetypes.guess_type(file_path)
        return mime_type or "image/jpeg"
    
    async def analyze_selected_image(self, query: str) -> str:
        """
        Complete pipeline: select image and analyze
        """
        try:
            # Step 1: Ask user to select image
            print("📁 Please select an image to analyze...")
            image_path = self.select_image_file()
            
            if not image_path:
                return "Image selection was cancelled."
            
            # Step 2: Validate the image
            print("🔍 Validating image...")
            validation = self.validate_image_file(image_path)
            
            if not validation["valid"]:
                return f"❌ Invalid image: {validation['error']}"
            
            # Step 3: Show confirmation dialog
            print("📋 Showing image preview...")
            confirmed = await self.confirm_image_selection(validation)
            
            if not confirmed:
                return "Image analysis cancelled by user."
            
            # Step 4: Read image file
            print("📖 Reading image file...")
            image_bytes = self.read_image_file(image_path)
            
            if not image_bytes:
                return "❌ Failed to read the image file."
            
            # Step 5: Translate query if needed
            
            
            if not is_english(query):
                translated_query = await translate_to_english_free(query)
                if translated_query:
                    query = translated_query
                    print(f"🔤 Translated query: {query}")
            
            # Step 6: Analyze with Gemini
            print(f"🤖 Analyzing image with Gemini AI...")
            mime_type = self.get_mime_type(image_path)
            result = await self.analyze_image(query, image_bytes, mime_type)
            
            # Add file info to result
            filename = Path(image_path).name
            file_info = f"\n\n📁 **Image File:** {filename}\n📏 **Dimensions:** {validation['dimensions'][0]} × {validation['dimensions'][1]}\n💾 **Size:** {validation['size_mb']:.2f} MB"
            
            return result + file_info
            
        except Exception as e:
            return f"❌ Image analysis failed: {str(e)}"


# Main function tool for LiveKit integration
@function_tool()
async def analyze_local_image(query: str = "What do you see in this image?") -> str:
    """
    Opens a file dialog for you to select an image from your computer, 
    then analyzes it using Google Gemini AI.
    
    Args:
        query: What you want to know about the image. Examples:
            - "What's in this image?"
            - "Describe this photo in detail"
            - "What text is written in this image?"
            - "Is this a real or AI-generated image?"
            - "What emotions does this image convey?"
            - "Where was this photo likely taken?"
    """
    try:
        # Initialize analyzer
        analyzer = GeminiImageAnalysis()
        
        # Perform analysis
        result = await analyzer.analyze_selected_image(query)
        
        return result
        
    except ValueError as e:
        return f"Configuration error: {str(e)}. Please set GOOGLE_API_KEY environment variable."
    except ImportError as e:
        return f"Missing dependency: {str(e)}. Please install Pillow: pip install Pillow"
    except Exception as e:
        return f"Error analyzing image: {str(e)}"


# Specialized image analysis tools
@function_tool()
async def identify_objects_in_image() -> str:
    """
    Select an image and identify all objects, people, and scenes in it
    """
    query = "Identify all objects, people, animals, buildings, vehicles, and scenes visible in this image. List them clearly with descriptions."
    return await analyze_local_image(query)


@function_tool()
async def extract_text_from_image() -> str:
    """
    Select an image and extract all readable text from it
    """
    query = "Extract and read ALL text visible in this image. Preserve the exact wording, formatting, and layout as much as possible. Include any labels, captions, signs, documents, or written content."
    return await analyze_local_image(query)


@function_tool()
async def analyze_photo_composition() -> str:
    """
    Select an image and analyze its photographic composition
    """
    query = "Analyze the photographic composition of this image. Discuss lighting, colors, focus, framing, rule of thirds, symmetry, leading lines, depth of field, and overall aesthetic quality."
    return await analyze_local_image(query)


@function_tool()
async def detect_image_authenticity() -> str:
    """
    Select an image and check if it's real or AI-generated/edited
    """
    query = "Analyze this image for authenticity. Is it likely a real photograph, AI-generated, or digitally edited? Look for telltale signs like unnatural lighting, inconsistent shadows, texture anomalies, facial irregularities, or pattern repetitions."
    return await analyze_local_image(query)


@function_tool()
async def describe_image_for_visually_impaired() -> str:
    """
    Select an image and get a detailed description suitable for visually impaired users
    """
    query = "Provide a detailed, descriptive analysis of this image suitable for someone who cannot see it. Describe the scene, colors, objects, people, actions, emotions, and overall context in a clear, comprehensive way."
    return await analyze_local_image(query)


@function_tool()
async def get_image_color_analysis() -> str:
    """
    Select an image and analyze its color palette and scheme
    """
    query = "Analyze the color palette of this image. Identify dominant colors, color harmony, color temperature (warm/cool), saturation levels, contrast, and overall color scheme. Mention specific color percentages if possible."
    return await analyze_local_image(query)


# Batch image analysis (analyze multiple images)
@function_tool()
async def compare_images(query: str = "Compare these two images") -> str:
    """
    Select multiple images and compare them
    Returns after analyzing two images
    """
    try:
        analyzer = GeminiImageAnalysis()
        results = []
        
        for i in range(2):  # Compare two images
            print(f"\n📁 Please select image {i+1} of 2...")
            image_path = analyzer.select_image_file()
            
            if not image_path:
                return f"Image {i+1} selection was cancelled."
            
            # Validate
            validation = analyzer.validate_image_file(image_path)
            if not validation["valid"]:
                return f"❌ Invalid image {i+1}: {validation['error']}"
            
            # Confirm
            confirmed = await analyzer.confirm_image_selection(validation)
            if not confirmed:
                return f"Image {i+1} analysis cancelled."
            
            # Read image
            image_bytes = analyzer.read_image_file(image_path)
            if not image_bytes:
                return f"❌ Failed to read image {i+1}."
            
            # Store for comparison
            results.append({
                'bytes': image_bytes,
                'mime_type': analyzer.get_mime_type(image_path),
                'filename': Path(image_path).name
            })
        
        # Combine images for comparison
        combined_query = f"""
        Compare these two images:
        
        1. {results[0]['filename']}
        2. {results[1]['filename']}
        
        Question: {query}
        
        Provide a detailed comparison including similarities, differences, themes, styles, and any other relevant aspects.
        """
        
        # Prepare payload with both images
        contents = {
            "contents": [{
                "parts": [
                    {"text": combined_query},
                    {
                        "inline_data": {
                            "mime_type": results[0]['mime_type'],
                            "data": base64.b64encode(results[0]['bytes']).decode('utf-8')
                        }
                    },
                    {
                        "inline_data": {
                            "mime_type": results[1]['mime_type'],
                            "data": base64.b64encode(results[1]['bytes']).decode('utf-8')
                        }
                    }
                ]
            }]
        }
        
        # Send to Gemini
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": analyzer.api_key
        }
        
        url = f"{analyzer.base_url}/{analyzer.model}:generateContent"
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=analyzer.config.timeout)) as session:
            async with session.post(url, json=contents, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    if "candidates" in data and len(data["candidates"]) > 0:
                        candidate = data["candidates"][0]
                        if "content" in candidate and "parts" in candidate["content"]:
                            parts = candidate["content"]["parts"]
                            if len(parts) > 0 and "text" in parts[0]:
                                return parts[0]["text"].strip()
        
        return "Could not compare the images."
        
    except Exception as e:
        return f"❌ Image comparison failed: {str(e)}"

