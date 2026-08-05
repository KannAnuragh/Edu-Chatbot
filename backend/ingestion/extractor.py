"""
PDF and TXT Text Extractor.

Extracts text from files using PyMuPDF (fitz) for fast extraction.
Intelligently detects legacy non-Unicode Indic fonts (like FML/ML-TT) and
routes those specific pages through Tesseract OCR to ensure correct Unicode output.
"""

from typing import List, Tuple
import fitz  # PyMuPDF
import os
import re
import gc
import io
from PIL import Image
import pytesseract

from core.config import settings

def _detect_legacy_font(page: fitz.Page) -> bool:
    """
    Check if the page uses legacy non-Unicode Malayalam fonts.
    Looks for common legacy font prefixes in the page's font list.
    """
    legacy_keywords = ['fml', 'ml-tt', 'karthika', 'matweb', 'revathi', 'thoolika']
    fonts = page.get_fonts()
    for font in fonts:
        # font is a tuple: (xref, ext, type, basefont, name, enc)
        # We check the basefont and name fields (index 3 and 4)
        basefont = str(font[3]).lower() if len(font) > 3 and font[3] else ""
        name = str(font[4]).lower() if len(font) > 4 and font[4] else ""
        
        for keyword in legacy_keywords:
            if keyword in basefont or keyword in name:
                return True
    return False

def _local_ocr_page(page: fitz.Page) -> str:
    """
    Run Tesseract OCR on a specific PyMuPDF page.
    Renders the page to a high-res image and extracts text.
    """
    # Render page to an image (scale up for better OCR accuracy)
    matrix = fitz.Matrix(2, 2)
    pix = page.get_pixmap(matrix=matrix)
    
    # Convert PyMuPDF pixmap to Pillow Image
    if pix.alpha:
        img = Image.frombytes("RGBA", [pix.width, pix.height], pix.samples)
    else:
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        
    # Run Tesseract OCR (assuming mal and eng language packs are installed)
    text = pytesseract.image_to_string(img, lang='mal+eng')
    return text.strip()


def extract_text_from_file(file_path: str) -> Tuple[List[Tuple[int, str]], int]:
    """
    Extract text from a PDF or TXT file using PyMuPDF.
    Routes legacy font pages through Tesseract OCR automatically.
    """
    pages_text = []
    doc = None
    
    try:
        if file_path.lower().endswith(".txt"):
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            pages_text.append((1, content))
            return pages_text, 1
            
        else:
            doc = fitz.open(file_path)
            page_count = len(doc)
            
            for i, page in enumerate(doc, 1):
                # Check for legacy fonts on this page
                if _detect_legacy_font(page):
                    print(f"⚠️ [Extractor] Legacy font detected on page {i}. Routing to Tesseract OCR...", flush=True)
                    text = _local_ocr_page(page)
                else:
                    text = page.get_text("text").strip()
                
                if text:
                    text = text.replace('\x00', '')  # Remove null bytes
                    pages_text.append((i, text))
                    
            return pages_text, page_count
            
    except Exception as e:
        print(f"Extraction error for {file_path}: {e}")
        raise e
    finally:
        if doc is not None and hasattr(doc, 'close'):
            try:
                doc.close()
            except Exception:
                pass
        gc.collect()

