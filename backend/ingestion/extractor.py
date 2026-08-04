"""
PDF and TXT Text Extractor.

Extracts text from files using PyMuPDF for PDFs and standard I/O for TXT.
Automatically converts legacy Malayalam fonts (ML-TT*) to proper Unicode
using the libindic-payyans library — completely offline, zero API tokens.
"""

from typing import List, Tuple
import fitz  # PyMuPDF
import os
import re

from core.config import settings

# --- Lazy-loaded Payyans converter (initialized once) ---
_payyans_instance = None

def _get_payyans():
    """Lazy-load the Payyans converter to avoid import errors if not installed."""
    global _payyans_instance
    if _payyans_instance is None:
        try:
            from libindic.payyans import Payyans
            _payyans_instance = Payyans()
            print("✅ [PAYYANS] Font converter loaded successfully.", flush=True)
        except ImportError:
            print("⚠️ [PAYYANS] libindic-payyans not installed. Legacy font conversion disabled.", flush=True)
            return None
    return _payyans_instance


def _detect_legacy_font(page) -> str:
    """
    Detect if a PDF page uses a legacy Malayalam font (ML-TT*).
    Uses both font metadata and content heuristics.
    """
    try:
        # 1. Metadata check (full=False prevents expensive font binary parsing)
        fonts = page.get_fonts(full=False)
        for font_info in fonts:
            basefont = font_info[3] if len(font_info) > 3 else ""
            name = font_info[4] if len(font_info) > 4 else ""
            
            for font_str in [basefont, name]:
                if not font_str:
                    continue
                font_upper = font_str.upper().replace(" ", "").replace("-", "")
                if "MLTT" in font_upper or "FML" in font_upper:
                    return "ML-TTKarthika"  # Default to most common standard mapping
                    
        # 2. Content Heuristic check (Fallback if metadata is stripped/different)
        text = page.get_text("text")
        if text:
            # These specific extended ASCII characters are the hallmarks of FML/ML legacy fonts
            # used for Malayalam rendering instead of proper Unicode.
            signature_chars = {'∂', 'Ø', '¬', '®', '¿', 'ƒ', 'Ω', '°'}
            char_count = sum(1 for c in text if c in signature_chars)
            
            # If we see a high density of these characters, it's definitely a legacy Malayalam font
            if char_count > 10:
                print(f"🔤 [FONT DETECT] Content heuristic triggered! Found {char_count} legacy signature characters.", flush=True)
                return "ML-TTKarthika"
                
    except Exception as e:
        print(f"⚠️ [FONT DETECT] Error detecting fonts: {e}", flush=True)
    return ""


def _convert_legacy_text(text: str, font_name: str) -> str:
    """
    Convert legacy Malayalam ASCII text to proper Unicode using Payyans.
    
    Args:
        text: The garbled ASCII text extracted from the PDF
        font_name: The legacy font name (e.g. ML-TTKarthika)
    
    Returns:
        Converted Unicode Malayalam text, or original text if conversion fails.
    """
    converter = _get_payyans()
    if converter is None:
        return text
    
    try:
        converted = converter.ASCII2Unicode(text, font_name)
        if converted and len(converted.strip()) > 0:
            return converted
        return text
    except Exception as e:
        print(f"⚠️ [FONT CONVERT] Conversion failed for font '{font_name}': {e}", flush=True)
        return text


def extract_text_from_file(file_path: str) -> Tuple[List[Tuple[int, str]], int]:
    """
    Extract text from a PDF or TXT file.
    
    For PDFs with legacy Malayalam fonts (ML-TT*), automatically converts
    the garbled ASCII to proper Unicode Malayalam using Payyans.
    
    Args:
        file_path: Path to the file
        
    Returns:
        Tuple containing:
        - List of (page_number, extracted_text)
        - Total page count
    """
    pages_text = []
    
    try:
        if file_path.lower().endswith(".txt"):
            # Handle plain text files
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            pages_text.append((1, content))
            return pages_text, 1
            
        else:
            # Handle PDF files
            doc = fitz.open(file_path)
            page_count = len(doc)
            
            # Detect legacy font once from the first few pages
            detected_font = ""
            for check_page in range(min(3, page_count)):
                detected_font = _detect_legacy_font(doc[check_page])
                if detected_font:
                    print(f"🔤 [FONT DETECT] Legacy font detected: '{detected_font}' — will auto-convert to Unicode.", flush=True)
                    break
            
            if not detected_font:
                print(f"🔤 [FONT DETECT] No legacy Malayalam font detected. Using standard text extraction.", flush=True)
            
            for i, page in enumerate(doc, 1):
                # Extract text using blocks to preserve layout/reading order
                blocks = page.get_text("blocks")
                # Filter out image blocks (block_type 1 is image, 0 is text)
                text_blocks = [b for b in blocks if len(b) >= 7 and b[6] == 0]
                # Sort blocks by vertical position first (top to bottom), then horizontal position
                text_blocks.sort(key=lambda b: (b[1], b[0]))
                text = "\n\n".join(b[4].strip() for b in text_blocks if b[4].strip()).strip()
                
                # If legacy font detected, convert the extracted text
                if detected_font and text:
                    text = _convert_legacy_text(text, detected_font)
                    if i <= 3 or i % 50 == 0:
                        # Log progress for first few pages and every 50th page
                        preview = text[:80].replace('\n', ' ')
                        print(f"📝 [FONT CONVERT] Page {i}/{page_count}: {preview}...", flush=True)
                
                # Only add pages that actually have text
                if text:
                    text = text.replace('\x00', '')  # Remove null bytes
                    pages_text.append((i, text))
                    
            return pages_text, page_count
            
    except Exception as e:
        print(f"Extraction error for {file_path}: {e}")
        raise e
    finally:
        if 'doc' in locals() and hasattr(doc, 'close'):
            doc.close()
        
        import gc
        gc.collect()
