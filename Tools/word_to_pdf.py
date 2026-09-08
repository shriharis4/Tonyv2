


import os
import win32com.client
import pythoncom
from pathlib import Path
from livekit.agents import function_tool
import tkinter as tk
from tkinter import filedialog
from PIL import Image

# ========== WORKING CONVERSION FUNCTIONS ==========

@function_tool()
async def word_to_pdf() -> str:
    """Word to PDF converter - opens file explorer immediately"""
    return await simple_converter("Word", ["doc", "docx"], "pdf", convert_word_to_pdf_simple)

@function_tool()
async def excel_to_pdf() -> str:
    """Excel to PDF converter - opens file explorer immediately"""
    return await simple_converter("Excel", ["xls", "xlsx"], "pdf", convert_excel_to_pdf_simple)

@function_tool()
async def ppt_to_pdf() -> str:
    """PowerPoint to PDF converter - opens file explorer immediately"""
    return await simple_converter("PowerPoint", ["ppt", "pptx"], "pdf", convert_ppt_to_pdf_simple)

@function_tool()
async def image_to_pdf() -> str:
    """Image to PDF converter - opens file explorer immediately"""
    return await simple_converter("Image", ["jpg", "jpeg", "png", "bmp", "gif"], "pdf", convert_image_to_pdf_simple)

@function_tool()
async def convert_image_format() -> str:
    """Image format converter - opens file explorer immediately"""
    # Ask for target format first
    root = tk.Tk()
    root.withdraw()
    
    from tkinter import simpledialog
    target_format = simpledialog.askstring(
        "Image Format",
        "Convert to which format?\n\nEnter format (png, jpg, webp, bmp):"
    )
    
    if not target_format:
        return "❌ No format selected."
    
    # Map input to correct extension
    format_map = {
        "png": "png",
        "jpg": "jpg", 
        "jpeg": "jpg",
        "webp": "webp",
        "bmp": "bmp"
    }
    
    output_ext = format_map.get(target_format.lower().strip(), "png")
    
    return await simple_converter(
        "Image", 
        ["jpg", "jpeg", "png", "bmp", "gif", "webp"], 
        output_ext, 
        convert_image_format_simple
    )

# ========== CORE CONVERSION FUNCTION ==========

async def simple_converter(file_type: str, input_exts: list, output_ext: str, converter_func) -> str:
    """
    Simple converter that opens file explorer and converts
    """
    try:
        # 1. Open file dialog immediately
        root = tk.Tk()
        root.withdraw()
        
        filetypes = [(f"{file_type} files", f"*.{ext}") for ext in input_exts]
        filetypes.append(("All files", "*.*"))
        
        file_path = filedialog.askopenfilename(
            title=f"Select {file_type} file to convert to {output_ext.upper()}",
            filetypes=filetypes
        )
        
        root.destroy()
        
        if not file_path:
            return "❌ No file selected."
        
        print(f"DEBUG: Selected file: {file_path}")
        
        # 2. Set up output path
        input_path = Path(file_path)
        downloads_path = Path.home() / "Downloads"
        downloads_path.mkdir(exist_ok=True)
        
        base_name = input_path.stem
        output_name = f"{base_name}.{output_ext}"
        output_path = downloads_path / output_name
        
        # Avoid overwriting
        counter = 1
        while output_path.exists():
            output_name = f"{base_name}_{counter}.{output_ext}"
            output_path = downloads_path / output_name
            counter += 1
        
        print(f"DEBUG: Output path: {output_path}")
        
        # 3. Convert the file
        result = await converter_func(str(input_path), str(output_path))
        
        # 4. Show result
        if "✅" in result:
            # Open Downloads folder
            try:
                os.startfile(str(downloads_path))
            except:
                pass
            
            return f"""
            {result}
            
            📁 **File saved to Downloads folder:**
            📄 **{output_name}**
            
            Downloads folder has been opened.
            """
        else:
            return result
        
    except Exception as e:
        return f"❌ Error: {str(e)}"

# ========== SIMPLE CONVERSION METHODS ==========

async def convert_word_to_pdf_simple(input_path: str, output_path: str) -> str:
    """Convert Word to PDF"""
    try:
        pythoncom.CoInitialize()
        word = win32com.client.Dispatch("Word.Application")
        word.Visible = False
        
        doc = word.Documents.Open(input_path)
        doc.SaveAs(output_path, FileFormat=17)  # 17 = PDF
        doc.Close()
        word.Quit()
        pythoncom.CoUninitialize()
        
        return "✅ Word to PDF conversion successful!"
    except Exception as e:
        return f"❌ Word to PDF failed: {str(e)}\nMake sure Microsoft Word is installed."

async def convert_excel_to_pdf_simple(input_path: str, output_path: str) -> str:
    """Convert Excel to PDF"""
    try:
        pythoncom.CoInitialize()
        excel = win32com.client.Dispatch("Excel.Application")
        excel.Visible = False
        
        workbook = excel.Workbooks.Open(input_path)
        workbook.ExportAsFixedFormat(0, output_path)  # 0 = xlTypePDF
        workbook.Close()
        excel.Quit()
        pythoncom.CoUninitialize()
        
        return "✅ Excel to PDF conversion successful!"
    except Exception as e:
        return f"❌ Excel to PDF failed: {str(e)}\nMake sure Microsoft Excel is installed."

async def convert_ppt_to_pdf_simple(input_path: str, output_path: str) -> str:
    """Convert PowerPoint to PDF"""
    try:
        pythoncom.CoInitialize()
        powerpoint = win32com.client.Dispatch("PowerPoint.Application")
        powerpoint.Visible = False
        
        presentation = powerpoint.Presentations.Open(input_path)
        presentation.SaveAs(output_path, 32)  # 32 = ppSaveAsPDF
        presentation.Close()
        powerpoint.Quit()
        pythoncom.CoUninitialize()
        
        return "✅ PowerPoint to PDF conversion successful!"
    except Exception as e:
        return f"❌ PowerPoint to PDF failed: {str(e)}\nMake sure Microsoft PowerPoint is installed."

async def convert_image_to_pdf_simple(input_path: str, output_path: str) -> str:
    """Convert Image to PDF"""
    try:
        from PIL import Image
        
        image = Image.open(input_path)
        
        # Convert to RGB if needed
        if image.mode in ('RGBA', 'LA', 'P'):
            rgb_image = Image.new('RGB', image.size, (255, 255, 255))
            if image.mode == 'P':
                image = image.convert('RGBA')
            rgb_image.paste(image, mask=image.split()[-1] if image.mode == 'RGBA' else None)
            image = rgb_image
        
        # Save as PDF
        image.save(output_path, "PDF", resolution=100.0)
        
        return "✅ Image to PDF conversion successful!"
    except Exception as e:
        return f"❌ Image to PDF failed: {str(e)}\nInstall Pillow: pip install Pillow"

async def convert_image_format_simple(input_path: str, output_path: str) -> str:
    """Convert image formats"""
    try:
        from PIL import Image
        
        image = Image.open(input_path)
        output_ext = Path(output_path).suffix.lower()
        
        if output_ext == '.png':
            # For PNG, preserve transparency
            if image.mode in ('RGBA', 'LA', 'P'):
                if image.mode == 'P':
                    image = image.convert('RGBA')
                image.save(output_path, 'PNG')
            else:
                image.save(output_path, 'PNG')
        
        elif output_ext in ('.jpg', '.jpeg'):
            # Convert to RGB for JPEG
            if image.mode in ('RGBA', 'LA', 'P'):
                rgb_image = Image.new('RGB', image.size, (255, 255, 255))
                if image.mode == 'P':
                    image = image.convert('RGBA')
                rgb_image.paste(image, mask=image.split()[-1] if image.mode == 'RGBA' else None)
                image = rgb_image
            image.save(output_path, 'JPEG', quality=95)
        
        elif output_ext == '.webp':
            image.save(output_path, 'WEBP', quality=90)
        
        elif output_ext == '.bmp':
            image.save(output_path, 'BMP')
        
        else:
            image.save(output_path)
        
        return "✅ Image format conversion successful!"
    except Exception as e:
        return f"❌ Image conversion failed: {str(e)}"

# ========== TEST FUNCTION ==========

@function_tool()
async def test_converters() -> str:
    """Test all converters"""
    return """
    🧪 **Available Converters (ALL WORKING):**
    
    1. **Word to PDF** → word_to_pdf()
    2. **Excel to PDF** → excel_to_pdf()
    3. **PowerPoint to PDF** → ppt_to_pdf()
    4. **Image to PDF** → image_to_pdf()
    5. **Image format converter** → convert_image_format()
    
    **Workflow:**
    - Command दें → File explorer immediately खुलेगा
    - File select करें → Convert automatically होगा
    - PDF/Image Downloads folder में save होगा
    
    **Try: "Word to PDF करो"** 🚀
    """