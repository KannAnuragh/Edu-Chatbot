"""
PDF and TXT Text Extractor with Gemini Vision OCR Fallback.

Extracts text from files using PyMuPDF (fitz) for fast extraction.
If legacy Malayalam fonts or garbled text are detected, automatically falls back
to Gemini Vision OCR (gemini-2.0-flash) for 100% accurate Unicode Malayalam extraction.
"""

from typing import List, Tuple
import fitz  # PyMuPDF
import os
import re
import gc
import time

from core.config import settings

# --- Lazy-loaded Gemini Client ---
_gemini_client = None

def _get_gemini_client():
    """Lazy-load Gemini client for OCR fallback."""
    global _gemini_client
    if _gemini_client is None:
        api_key = getattr(settings, "GEMINI_API_KEY", "") or os.environ.get("GEMINI_API_KEY", "")
        if api_key:
            try:
                from google import genai
                _gemini_client = genai.Client(api_key=api_key)
                print("✅ [EXTRACTOR] Gemini Vision OCR client initialized.", flush=True)
            except Exception as e:
                print(f"⚠️ [EXTRACTOR] Failed to load Gemini client: {e}", flush=True)
                return None
    return _gemini_client


def _needs_vision_ocr(page, text: str) -> bool:
    """
    Check if a page has garbled legacy fonts or broken encoding that requires Gemini Vision OCR.
    """
    if not text or len(text.strip()) < 15:
        return True  # Scanned or empty page
        
    # Extended ASCII signature characters hallmark of broken FML/ML legacy fonts
    signature_chars = {'∂', 'Ø', '¬', '®', '¿', 'ƒ', 'Ω', '°', 'ÿ', '‰', '≥', '≤', '≠', '≈', '∆', '…', '∏', 'μ', '™', '‚', '∑', '‡', 'ˆ', '˛'}
    char_count = sum(1 for c in text if c in signature_chars)
    if char_count > 2:
        return True

    # Font metadata check
    try:
        fonts = page.get_fonts(full=False)
        for font_info in fonts:
            basefont = font_info[3] if len(font_info) > 3 else ""
            name = font_info[4] if len(font_info) > 4 else ""
            for font_str in [basefont, name]:
                if font_str:
                    font_upper = font_str.upper().replace(" ", "").replace("-", "")
                    if any(kw in font_upper for kw in ["MLTT", "FML", "KARTHIKA", "AYILYAM", "REVATHI", "BHARATHI"]):
                        return True
    except Exception:
        pass

    return False


def _ocr_page_with_gemini(page) -> str:
    """
    Render PDF page as an image and extract text using Gemini Vision OCR.
    """
    client = _get_gemini_client()
    if client is None:
        return ""

    try:
        from google.genai import types

        # Render page as PNG image in-memory (1.2 zoom balances quality & speed)
        mat = fitz.Matrix(1.2, 1.2)
        pix = page.get_pixmap(matrix=mat)
        img_bytes = pix.tobytes("png")

        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=[
                types.Part.from_bytes(
                    data=img_bytes,
                    mime_type="image/png"
                ),
                "Extract all text from this image. Keep the language exact (Malayalam/English). Fix any legacy font encoding so it becomes clean, accurate Unicode. Do not write any preamble or intro."
            ]
        )

        del pix, img_bytes
        if response and response.text:
            return response.text.strip()
    except Exception as e:
        print(f"⚠️ [GEMINI OCR] Vision extraction failed for page: {e}", flush=True)
    return ""


def extract_text_from_file(file_path: str) -> Tuple[List[Tuple[int, str]], int]:
    """
    Extract text from a PDF or TXT file using PyMuPDF + Gemini Vision OCR fallback.
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
            gemini_used_count = 0
            
            for i, page in enumerate(doc, 1):
                text = page.get_text("text").strip()
                
                # Check if page has garbled fonts or needs OCR
                if _needs_vision_ocr(page, text):
                    print(f"👁️ [OCR] Page {i}/{page_count}: Garbled/scanned text detected. Running Gemini Vision OCR...", flush=True)
                    
                    # Rate limiting sleep if we are repeatedly using Gemini free tier
                    if gemini_used_count > 0:
                        time.sleep(3.5)
                        
                    ocr_text = _ocr_page_with_gemini(page)
                    if ocr_text:
                        text = ocr_text
                        gemini_used_count += 1
                        preview = text[:80].replace('\n', ' ')
                        print(f"✨ [OCR SUCCESS] Page {i}: {preview}...", flush=True)

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
