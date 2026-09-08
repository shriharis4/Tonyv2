import pyautogui
import asyncio
import aiohttp
import json
import re
import logging
import random
import time
import sys
import os
from typing import Dict, List, Optional, Tuple, Any, Set
from dataclasses import dataclass
from livekit.agents import function_tool
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Try importing OCR libraries independently so missing optional packages do not break app startup.
Image = None
ImageGrab = None
ImageEnhance = None
ImageFilter = None
ImageOps = None
ImageDraw = None
pytesseract = None
cv2 = None
np = None

try:
    from PIL import ImageGrab, Image, ImageEnhance, ImageFilter, ImageOps, ImageDraw
except ImportError as e:
    logger.warning(f"Pillow not available: {e}")

try:
    import pytesseract
except ImportError as e:
    logger.warning(f"pytesseract not available: {e}")

try:
    import cv2
except ImportError as e:
    logger.warning(f"cv2 not available: {e}")

try:
    import numpy as np
except ImportError as e:
    logger.warning(f"numpy not available: {e}")

OCR_AVAILABLE = all([
    Image is not None,
    pytesseract is not None,
    cv2 is not None,
    np is not None,
])

# ==================== TRANSLATION FUNCTIONS ====================

async def translate_to_english_free(text: str) -> str:
    """Translate text to English using free APIs"""
    if not text.strip():
        return text
    
    # Check if text is already in English
    if is_english(text):
        return text
    
    # Try multiple translation services
    services = [
        try_google_translate,
        try_my_memory_translate,
        try_libretranslate
    ]
    
    for service in services:
        try:
            translation = await service(text)
            if translation and translation.strip() and translation.lower() != text.lower():
                logger.info(f"Translated '{text}' to '{translation}'")
                return translation
        except Exception as e:
            logger.debug(f"Translation service failed: {e}")
            continue
    
    # Fallback to basic dictionary
    return fallback_translation(text)

def is_english(text: str) -> bool:
    """Check if text is already in English"""
    try:
        # Count non-ASCII characters
        non_ascii_count = sum(1 for char in text if ord(char) > 127)
        return (non_ascii_count / max(len(text), 1)) < 0.3  # Less than 30% non-ASCII
    except:
        return True

async def try_google_translate(text: str) -> Optional[str]:
    """Google Translate"""
    try:
        url = "https://translate.googleapis.com/translate_a/single"
        params = {
            'client': 'gtx',
            'sl': 'auto',
            'tl': 'en',
            'dt': 't',
            'q': text[:500]  # Limit length
        }
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if data and len(data) > 0:
                        translated_parts = []
                        for part in data[0]:
                            if part[0]:
                                translated_parts.append(part[0])
                        return ''.join(translated_parts)
    except Exception as e:
        logger.debug(f"Google Translate error: {e}")
    return None

async def try_my_memory_translate(text: str) -> Optional[str]:
    """MyMemory Translation"""
    try:
        url = "https://api.mymemory.translated.net/get"
        params = {
            'q': text[:500],
            'langpair': 'auto|en'
        }
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('responseStatus') == 200:
                        return data['responseData']['translatedText']
    except Exception as e:
        logger.debug(f"MyMemory error: {e}")
    return None

async def try_libretranslate(text: str) -> Optional[str]:
    """LibreTranslate"""
    try:
        instances = [
            "https://translate.argosopentech.com/translate",
            "https://libretranslate.de/translate",
        ]
        
        payload = {
            'q': text[:500],
            'source': 'auto',
            'target': 'en',
            'format': 'text'
        }
        
        headers = {'Content-Type': 'application/json'}
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
            for instance_url in instances:
                try:
                    async with session.post(instance_url, 
                                          data=json.dumps(payload), 
                                          headers=headers) as response:
                        if response.status == 200:
                            data = await response.json()
                            return data.get('translatedText')
                except:
                    continue
    except Exception as e:
        logger.debug(f"LibreTranslate error: {e}")
    return None

def fallback_translation(text: str) -> str:
    """Basic fallback translation"""
    translations = {
        # Hindi to English
        "नमस्ते": "hello", "हैलो": "hello", "कैसे": "how", "हो": "are", 
        "आप": "you", "तुम": "you", "मैं": "I", "मेरा": "my", "नाम": "name",
        "लिखो": "write", "टाइप": "type", "दिखाओ": "show", "खोलो": "open",
        "क्लिक": "click", "बटन": "button", "मेनू": "menu", "फाइल": "file",
        "सेटिंग": "setting", "विकल्प": "option", "सहेजें": "save", "बंद": "close",
        "प्रारंभ": "start", "समाप्त": "end", "रद्द": "cancel", "ठीक": "ok",
        "हाँ": "yes", "नहीं": "no", "धन्यवाद": "thank you",
        "सुमित": "sumit", "सुनील": "sunil", "राजेश": "rajesh", "मोहन": "mohan",
        "कुमार": "kumar", "सिंह": "singh", "वर्मा": "verma", "शर्मा": "sharma",
        
        # Common UI elements
        "सबमिट": "submit", "अगला": "next", "पिछला": "previous", "जारी": "continue",
        "रोकें": "stop", "प्ले": "play", "पॉज": "pause", "वापस": "back",
        "आगे": "forward", "ताजा": "refresh", "अपडेट": "update", "इंस्टॉल": "install",
        "अनइंस्टॉल": "uninstall", "डाउनलोड": "download", "अपलोड": "upload",
        "संपादित": "edit", "हटाएं": "delete", "प्रतिलिपि": "copy", "चिपकाएं": "paste",
        "काटें": "cut", "चुनें": "select", "सभी": "all", "कुछ": "some",
        "नया": "new", "पुराना": "old", "बड़ा": "big", "छोटा": "small",
        "तेज": "fast", "धीमा": "slow", "आसान": "easy", "कठिन": "hard",
        "मुफ्त": "free", "भुगतान": "paid", "सुरक्षित": "safe", "खतरनाक": "dangerous"
    }
    
    words = text.split()
    translated = []
    
    for word in words:
        clean = word.strip('.,!?;:"').lower()
        if clean in translations:
            translated.append(translations[clean])
        else:
            translated.append(word)
    
    result = ' '.join(translated)
    if result and result[0].isalpha():
        result = result[0].upper() + result[1:]
    
    return result

# ==================== ADVANCED OCR PROCESSOR ====================

@dataclass
class TextItem:
    """Enhanced text item with more metadata"""
    text: str
    x: int
    y: int
    w: int
    h: int
    confidence: float
    source: str = ""
    preprocess_method: str = ""
    page_num: int = 1
    block_num: int = 1
    line_num: int = 1
    word_num: int = 1

class AdvancedOCRProcessor:
    """Advanced OCR with multiple preprocessing techniques"""
    
    _cache: Dict[str, Tuple[List[TextItem], float]] = {}
    CACHE_DURATION = 3.0
    
    # Text correction patterns
    CORRECTION_PATTERNS = [
        (r'\|', 'I'),
        (r'\[', 'I'),
        (r'\]', 'I'),
        (r'\(', 'C'),
        (r'\)', 'C'),
        (r'0(?=[A-Za-z])', 'O'),
        (r'1(?=[A-Za-z])', 'I'),
        (r'5(?=[A-Za-z])', 'S'),
        (r'8(?=[A-Za-z])', 'B'),
        (r'\$', 'S'),
        (r'@', 'a'),
        (r'&', 'and'),
        (r'\s+', ' '),
        (r'^[^a-zA-Z0-9]+', ''),  # Remove leading non-alphanumeric
        (r'[^a-zA-Z0-9\s.,!?-]+$', ''),  # Remove trailing special chars
    ]
    
    @staticmethod
    def get_cache_key(region: Optional[Tuple[int, int, int, int]] = None) -> str:
        """Generate unique cache key"""
        width, height = pyautogui.size()
        key = f"screen_{width}x{height}_{datetime.now().strftime('%H%M')}"
        if region:
            key += f"_r{region[0]}_{region[1]}_{region[2]}_{region[3]}"
        return key
    
    @staticmethod
    def clear_old_cache():
        """Remove expired cache entries"""
        current = time.time()
        expired = [k for k, (_, t) in AdvancedOCRProcessor._cache.items() 
                  if current - t > AdvancedOCRProcessor.CACHE_DURATION]
        for k in expired:
            del AdvancedOCRProcessor._cache[k]
    
    @staticmethod
    def preprocess_image(image: Image.Image, method: str = "auto") -> List[Tuple[Image.Image, str, Dict]]:
        """Generate multiple preprocessed images for better OCR"""
        processed = []
        
        # Convert to RGB if needed
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Convert PIL to OpenCV
        cv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        
        # Method 1: Original
        processed.append((image.copy(), "original", {'psm': 7, 'oem': 3}))
        
        # Method 2: Grayscale
        gray = image.convert('L')
        processed.append((gray, "grayscale", {'psm': 7, 'oem': 3}))
        
        # Method 3: Enhanced contrast
        enhancer = ImageEnhance.Contrast(gray)
        high_contrast = enhancer.enhance(2.0)
        processed.append((high_contrast, "high_contrast", {'psm': 8, 'oem': 3}))
        
        # Method 4: Thresholded
        _, thresh = cv2.threshold(cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY), 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        thresh_pil = Image.fromarray(thresh)
        processed.append((thresh_pil, "threshold", {'psm': 11, 'oem': 3}))
        
        # Method 5: Denoised
        denoised = cv2.fastNlMeansDenoisingColored(cv_image, None, 10, 10, 7, 21)
        denoised_pil = Image.fromarray(cv2.cvtColor(denoised, cv2.COLOR_BGR2RGB))
        processed.append((denoised_pil, "denoised", {'psm': 7, 'oem': 3}))
        
        # Method 6: Sharpened
        kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
        sharpened = cv2.filter2D(cv_image, -1, kernel)
        sharpened_pil = Image.fromarray(cv2.cvtColor(sharpened, cv2.COLOR_BGR2RGB))
        processed.append((sharpened_pil, "sharpened", {'psm': 7, 'oem': 3}))
        
        # Method 7: Inverted
        inverted = ImageOps.invert(gray)
        processed.append((inverted, "inverted", {'psm': 7, 'oem': 3}))
        
        return processed
    
    @staticmethod
    def enhance_corners(image: Image.Image) -> Image.Image:
        """Specifically enhance corner regions"""
        width, height = image.size
        corner_size = min(300, width // 4, height // 4)
        
        # Create a copy
        enhanced = image.copy()
        
        # Define corners
        corners = [
            (0, 0, corner_size, corner_size),  # Top-left
            (width - corner_size, 0, width, corner_size),  # Top-right
            (0, height - corner_size, corner_size, height),  # Bottom-left
            (width - corner_size, height - corner_size, width, height)  # Bottom-right
        ]
        
        for x1, y1, x2, y2 in corners:
            corner = image.crop((x1, y1, x2, y2))
            
            # Enhance this corner
            corner_gray = corner.convert('L')
            enhancer = ImageEnhance.Contrast(corner_gray)
            enhanced_corner = enhancer.enhance(2.5)
            enhancer = ImageEnhance.Brightness(enhanced_corner)
            enhanced_corner = enhancer.enhance(1.3)
            
            # Paste back
            enhanced.paste(enhanced_corner, (x1, y1))
        
        return enhanced
    
    @staticmethod
    def clean_text(text: str) -> str:
        """Clean and correct OCR text"""
        if not text:
            return ""
        
        # Initial cleaning
        text = text.strip()
        
        # Apply correction patterns
        for pattern, replacement in AdvancedOCRProcessor.CORRECTION_PATTERNS:
            text = re.sub(pattern, replacement, text)
        
        # Remove isolated single characters (likely OCR errors)
        words = text.split()
        cleaned_words = []
        for word in words:
            if len(word) > 1 or word in ['I', 'a', 'A']:
                cleaned_words.append(word)
        
        text = ' '.join(cleaned_words)
        
        # Capitalize first letter if it's a sentence
        if text and text[0].isalpha():
            text = text[0].upper() + text[1:]
        
        return text
    
    @staticmethod
    def calculate_similarity(text1: str, text2: str, confidence: float = 100.0) -> float:
        """Calculate similarity between two texts"""
        if not text1 or not text2:
            return 0.0
        
        t1 = text1.lower().strip()
        t2 = text2.lower().strip()
        
        # 1. Exact match
        if t1 == t2:
            return 1.0
        
        # 2. Contains match
        if t1 in t2 or t2 in t1:
            return 0.9
        
        # 3. Word overlap
        words1 = set(t1.split())
        words2 = set(t2.split())
        
        if words1 and words2:
            # Jaccard similarity
            intersection = len(words1.intersection(words2))
            union = len(words1.union(words2))
            jaccard = intersection / union if union > 0 else 0
            
            if jaccard > 0.5:
                return 0.7 + (0.2 * jaccard)
        
        # 4. Levenshtein distance for short texts
        if len(t1) < 30 and len(t2) < 30:
            # Simplified Levenshtein
            if len(t1) > len(t2):
                t1, t2 = t2, t1
            
            distances = range(len(t1) + 1)
            for i2, c2 in enumerate(t2):
                distances_ = [i2 + 1]
                for i1, c1 in enumerate(t1):
                    if c1 == c2:
                        distances_.append(distances[i1])
                    else:
                        distances_.append(1 + min((distances[i1], distances[i1 + 1], distances_[-1])))
                distances = distances_
            
            distance = distances[-1]
            max_len = max(len(t1), len(t2))
            similarity = 1 - (distance / max_len)
            
            if similarity > 0.6:
                return 0.6 + (0.3 * similarity)
        
        # 5. Confidence-based score
        return min(0.5, confidence / 100.0)

async def extract_text_with_tesseract(image: Image.Image, config: Dict) -> List[TextItem]:
    """Extract text using Tesseract with specific config"""
    items = []
    
    try:
        # Build config string
        config_str = f'--psm {config.get("psm", 7)} --oem {config.get("oem", 3)}'
        config_str += ' -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.,!?-@#$%&*()[]{}<>/:; '
        config_str += ' -c preserve_interword_spaces=1'
        
        # Get data
        data = pytesseract.image_to_data(
            image,
            config=config_str,
            lang='eng+hin',  # Support English and Hindi
            output_type=pytesseract.Output.DICT,
            timeout=5
        )
        
        # Process results
        n_boxes = len(data['text'])
        for i in range(n_boxes):
            text = data['text'][i].strip()
            conf = float(data['conf'][i])
            
            if text and conf > 0 and len(text) >= 2:
                # Clean text
                clean_text = AdvancedOCRProcessor.clean_text(text)
                
                if clean_text:
                    items.append(TextItem(
                        text=clean_text,
                        x=data['left'][i],
                        y=data['top'][i],
                        w=data['width'][i],
                        h=data['height'][i],
                        confidence=conf,
                        source="tesseract",
                        preprocess_method=config.get('method', 'unknown'),
                        page_num=data.get('page_num', [1])[i],
                        block_num=data.get('block_num', [1])[i],
                        line_num=data.get('line_num', [1])[i],
                        word_num=data.get('word_num', [1])[i]
                    ))
    
    except Exception as e:
        logger.error(f"Tesseract extraction error: {e}")
    
    return items

async def find_text_on_screen(
    search_text: str,
    region: Optional[Tuple[int, int, int, int]] = None,
    min_confidence: int = 60,
    exact_match: bool = False,
    focus_corners: bool = False
) -> Tuple[Optional[TextItem], float, List[TextItem]]:
    """Main function to find text on screen"""
    
    if not OCR_AVAILABLE:
        raise ImportError("OCR libraries not available")
    
    # Clear old cache
    AdvancedOCRProcessor.clear_old_cache()
    
    # Get cache key
    cache_key = AdvancedOCRProcessor.get_cache_key(region)
    cached_items = []
    
    # Check cache
    if cache_key in AdvancedOCRProcessor._cache:
        cached_items, _ = AdvancedOCRProcessor._cache[cache_key]
    else:
        # Capture screen
        screenshot_time = time.time()
        
        if region:
            x, y, w, h = region
            screenshot = ImageGrab.grab(bbox=(x, y, x + w, y + h))
        else:
            screenshot = ImageGrab.grab()
        
        logger.info(f"Screenshot captured in {time.time() - screenshot_time:.2f}s")
        
        # Enhance corners if requested
        if focus_corners:
            screenshot = AdvancedOCRProcessor.enhance_corners(screenshot)
        
        # Preprocess images
        processed_images = AdvancedOCRProcessor.preprocess_image(screenshot)
        
        # Extract text from all processed versions
        tasks = []
        for img, method, config in processed_images:
            config['method'] = method
            task = extract_text_with_tesseract(img, config)
            tasks.append(task)
        
        # Run OCR in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Combine and deduplicate results
        seen_positions = set()
        for result in results:
            if isinstance(result, list):
                for item in result:
                    if item.confidence >= min_confidence:
                        # Deduplicate by position and text
                        pos_key = f"{item.x//10}_{item.y//10}_{item.text[:20].lower()}"
                        if pos_key not in seen_positions:
                            seen_positions.add(pos_key)
                            cached_items.append(item)
        
        # Cache results
        if cached_items:
            AdvancedOCRProcessor._cache[cache_key] = (cached_items, time.time())
            logger.info(f"Found {len(cached_items)} text items, cached")
    
    if not cached_items:
        return None, 0.0, []
    
    # Find best match
    best_item = None
    best_score = 0.0
    good_matches = []
    
    search_lower = search_text.lower().strip()
    
    for item in cached_items:
        # Calculate similarity
        score = AdvancedOCRProcessor.calculate_similarity(
            search_text, item.text, item.confidence
        )
        
        # Apply thresholds
        threshold = 0.85 if exact_match else 0.65
        
        if score >= threshold:
            good_matches.append((item, score))
            
            if score > best_score:
                best_score = score
                best_item = item
    
    # If no good matches, try lower threshold
    if not best_item and good_matches:
        good_matches.sort(key=lambda x: x[1], reverse=True)
        best_item, best_score = good_matches[0]
        if best_score < 0.5:
            best_item = None
    
    return best_item, best_score, cached_items

# ==================== MAIN CLICK FUNCTION ====================

@function_tool()
async def click_on_screen_text(
    command: str,
    min_confidence: int = 60,
    use_cache: bool = True,
    region_x: Optional[int] = None,
    region_y: Optional[int] = None,
    region_width: Optional[int] = None,
    region_height: Optional[int] = None,
    exact_match: bool = False,
    highlight_corners: bool = False,
    double_click: bool = False,
    right_click: bool = False,  # Fixed: Added default value
    scroll_amount: int = 0
) -> str:
    """
    Advanced text finding and clicking with multiple improvements.
    
    Args:
        command: Text to find and click
        min_confidence: Minimum OCR confidence (0-100)
        use_cache: Use text cache for faster operation
        region_x, region_y, region_width, region_height: Search region
        exact_match: Require exact text match
        highlight_corners: Focus on corner regions
        double_click: Perform double click
        right_click: Right click instead of left click
        scroll_amount: Scroll after clicking (positive for down, negative for up)
    
    Returns:
        Status message
    """
    
    # Check OCR availability
    if not OCR_AVAILABLE:
        install_instructions = """
        Install required packages:
        pip install pytesseract pillow opencv-python pyautogui
        
        Also install Tesseract OCR:
        Windows: https://github.com/UB-Mannheim/tesseract/wiki
        Mac: brew install tesseract
        Linux: sudo apt-get install tesseract-ocr
        """
        return f"OCR libraries not available.\n{install_instructions}"
        
    # Check Tesseract binary availability
    try:
        pytesseract.get_tesseract_version()
    except Exception as e:
        return ("❌ Tesseract OCR is not installed or not in your system PATH.\n"
                "Please install Tesseract OCR from: https://github.com/UB-Mannheim/tesseract/wiki "
                "and ensure the installation directory is added to your environment variables PATH.")
    
    start_time = time.time()
    
    # Clean and translate command
    original_command = command.strip()
    if not original_command:
        return "Error: No search text provided."
    
    logger.info(f"Searching for: '{original_command}'")
    
    # Translate if needed
    translated_command = await translate_to_english_free(original_command)
    if translated_command != original_command:
        logger.info(f"Translated to: '{translated_command}'")
    
    search_command = translated_command
    
    try:
        # Setup region
        region = None
        if all(v is not None for v in [region_x, region_y, region_width, region_height]):
            region = (region_x, region_y, region_width, region_height)
            logger.info(f"Searching in region: {region}")
        
        # If focusing on corners, search each corner separately
        if highlight_corners and not region:
            screen_width, screen_height = pyautogui.size()
            corner_size = min(400, screen_width // 3, screen_height // 3)
            
            corners = [
                (0, 0, corner_size, corner_size),  # Top-left
                (screen_width - corner_size, 0, corner_size, corner_size),  # Top-right
                (0, screen_height - corner_size, corner_size, corner_size),  # Bottom-left
                (screen_width - corner_size, screen_height - corner_size, corner_size, corner_size)  # Bottom-right
            ]
            
            for i, corner in enumerate(corners):
                logger.info(f"Searching corner {i+1}: {corner}")
                match, score, _ = await find_text_on_screen(
                    search_command, corner, min_confidence, exact_match, False
                )
                
                if match and score >= 0.7:
                    # Calculate absolute coordinates
                    click_x = corner[0] + match.x + match.w // 2
                    click_y = corner[1] + match.y + match.h // 2
                    
                    return await perform_advanced_click(
                        click_x, click_y, match, score, start_time,
                        double_click, right_click, scroll_amount
                    )
        
        # Normal search
        match, score, all_items = await find_text_on_screen(
            search_command, region, min_confidence, exact_match, highlight_corners
        )
        
        if not match:
            # Provide helpful suggestions
            if all_items:
                # Group similar items
                suggestions = {}
                for item in all_items:
                    if item.confidence >= min_confidence:
                        key = item.text[:30].lower()
                        if key not in suggestions or item.confidence > suggestions[key][0].confidence:
                            suggestions[key] = item
                
                # Show top suggestions
                top_items = list(suggestions.values())[:10]
                suggestion_text = "\n".join(
                    f"• '{item.text}' (conf: {item.confidence:.0f}%, pos: {item.x},{item.y})"
                    for item in sorted(top_items, key=lambda x: x.confidence, reverse=True)
                )
                
                match_type = "exact" if exact_match else "similar"
                return (f"No {match_type} match found for '{original_command}'.\n"
                       f"Top suggestions:\n{suggestion_text}")
            else:
                return f"No readable text found (min confidence: {min_confidence}%)."
        
        # Calculate click position
        if region:
            click_x = region[0] + match.x + match.w // 2
            click_y = region[1] + match.y + match.h // 2
        else:
            click_x = match.x + match.w // 2
            click_y = match.y + match.h // 2
        
        # Add small random offset for human-like clicking
        click_x += random.randint(-2, 2)
        click_y += random.randint(-2, 2)
        
        return await perform_advanced_click(
            click_x, click_y, match, score, start_time,
            double_click, right_click, scroll_amount
        )
        
    except pytesseract.TesseractNotFoundError:
        return ("Tesseract OCR not installed.\n"
                "Download from: https://github.com/tesseract-ocr/tesseract")
    
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return f"Error: {str(e)}"

async def perform_advanced_click(
    x: int, y: int,
    match: TextItem,
    score: float,
    start_time: float,
    double_click: bool = False,
    right_click: bool = False,
    scroll_amount: int = 0
) -> str:
    """Perform the click with advanced options"""
    
    try:
        # Safety checks
        screen_width, screen_height = pyautogui.size()
        if not (0 <= x < screen_width and 0 <= y < screen_height):
            return f"Coordinates ({x}, {y}) outside screen bounds ({screen_width}x{screen_height})."
        
        # Move mouse with natural motion
        current_x, current_y = pyautogui.position()
        
        # Calculate distance for speed adjustment
        distance = ((x - current_x) ** 2 + (y - current_y) ** 2) ** 0.5
        duration = min(0.5, max(0.1, distance / 1000))
        
        # Move to position
        pyautogui.moveTo(x, y, duration=duration, tween=pyautogui.easeInOutQuad)
        await asyncio.sleep(0.05)  # Small pause
        
        # Perform click
        if right_click:
            pyautogui.rightClick()
            click_type = "right-clicked"
        elif double_click:
            pyautogui.doubleClick()
            click_type = "double-clicked"
        else:
            pyautogui.click()
            click_type = "clicked"
        
        # Scroll if requested
        if scroll_amount != 0:
            await asyncio.sleep(0.1)
            pyautogui.scroll(scroll_amount)
            scroll_text = f", scrolled {abs(scroll_amount)} lines {'down' if scroll_amount > 0 else 'up'}"
        else:
            scroll_text = ""
        
        # Calculate total time
        total_time = time.time() - start_time
        
        # Return success message
        return (f"✅ {click_type} on '{match.text}' "
               f"(Score: {score:.2f}, Confidence: {match.confidence:.0f}%, "
               f"Time: {total_time:.1f}s{scroll_text})")
        
    except pyautogui.FailSafeException:
        return "⚠️ Fail-safe triggered (mouse at screen corner). Move mouse and retry."
    
    except Exception as e:
        return f"Click error: {str(e)}"

# ==================== SIMPLIFIED VERSION (For LiveKit Compatibility) ====================

@function_tool()
async def click_text(
    command: str,
    min_confidence: int = 60,
    exact_match: bool = False,
    highlight_corners: bool = False,
    double_click: bool = False,
    right_click: bool = False
) -> str:
    """
    Simplified version for LiveKit with all required parameters.
    
    Args:
        command: Text to find and click
        min_confidence: OCR confidence threshold (0-100)
        exact_match: Require exact text match
        highlight_corners: Focus on corner regions
        double_click: Perform double click
        right_click: Perform right click
    
    Returns:
        Status message
    """
    # Call the main function with default values for optional parameters
    return await click_on_screen_text(
        command=command,
        min_confidence=min_confidence,
        use_cache=True,
        region_x=None,
        region_y=None,
        region_width=None,
        region_height=None,
        exact_match=exact_match,
        highlight_corners=highlight_corners,
        double_click=double_click,
        right_click=right_click,
        scroll_amount=0
    )

# ==================== ADDITIONAL UTILITY FUNCTIONS ====================

@function_tool()
async def find_all_text(
    min_confidence: int = 50,
    region_x: Optional[int] = None,
    region_y: Optional[int] = None,
    region_width: Optional[int] = None,
    region_height: Optional[int] = None
) -> str:
    """Find all text on screen"""
    try:
        region = None
        if all(v is not None for v in [region_x, region_y, region_width, region_height]):
            region = (region_x, region_y, region_width, region_height)
        
        _, _, all_items = await find_text_on_screen("", region, min_confidence, False)
        
        if not all_items:
            return "No text found."
        
        # Group by approximate position
        grouped = {}
        for item in all_items:
            group_key = f"{item.y // 50}"  # Group by vertical position
            if group_key not in grouped:
                grouped[group_key] = []
            grouped[group_key].append(item)
        
        # Format output
        lines = [f"Found {len(all_items)} text items:"]
        for y_key in sorted(grouped.keys()):
            items = grouped[y_key]
            items.sort(key=lambda x: x.x)
            for item in items:
                lines.append(f"  '{item.text}' (conf: {item.confidence:.0f}%, pos: {item.x},{item.y})")
        
        return "\n".join(lines)
        
    except Exception as e:
        return f"Error: {str(e)}"

@function_tool()
async def verify_ocr_setup() -> str:
    """Verify OCR setup is working correctly"""
    checks = []
    
    # Check imports
    try:
        import pytesseract
        checks.append("✓ pytesseract imported")
    except ImportError:
        checks.append("✗ pytesseract not installed")
    
    try:
        from PIL import Image
        checks.append("✓ PIL imported")
    except ImportError:
        checks.append("✗ PIL not installed")
    
    try:
        import cv2
        checks.append("✓ OpenCV imported")
    except ImportError:
        checks.append("✗ OpenCV not installed")
    
    # Check Tesseract executable
    try:
        pytesseract.get_tesseract_version()
        checks.append("✓ Tesseract found")
    except Exception as e:
        checks.append(f"✗ Tesseract error: {e}")
    
    # Test screenshot
    try:
        from PIL import ImageGrab
        img = ImageGrab.grab()
        checks.append(f"✓ Screenshot captured ({img.size[0]}x{img.size[1]})")
    except Exception as e:
        checks.append(f"✗ Screenshot failed: {e}")
    
    return "OCR Setup Check:\n" + "\n".join(checks)

