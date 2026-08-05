"""
PDF and TXT Text Extractor.

Extracts text from files using PyMuPDF (fitz) for high-speed, low-memory PDF extraction.
Automatically converts legacy Malayalam fonts (ML-TT*) to proper Unicode
using the libindic-payyans library — completely offline, zero API tokens.
"""

from typing import List, Tuple
import fitz  # PyMuPDF
import os
import re
import gc

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


def _detect_legacy_font(page, text: str) -> str:
    """
    Detect if a PDF page uses a legacy Malayalam font (ML-TT*, FML*).
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
                if any(kw in font_upper for kw in ["MLTT", "FML", "KARTHIKA", "AYILYAM", "REVATHI", "BHARATHI"]):
                    return "ML-TTKarthika"  # Default to most common standard mapping
                    
        # 2. Content Heuristic check (Fallback if metadata is stripped/different)
        if text:
            # Extended ASCII characters hallmark of FML/ML legacy fonts
            signature_chars = {'∂', 'Ø', '¬', '®', '¿', 'ƒ', 'Ω', '°', 'ÿ', '‰', '≥', '≤', '≠', '≈', '∆', '…'}
            char_count = sum(1 for c in text if c in signature_chars)
            
            if char_count > 3:
                print(f"🔤 [FONT DETECT] Content heuristic triggered! Found {char_count} legacy signature characters.", flush=True)
                return "ML-TTKarthika"
                
    except Exception as e:
        print(f"⚠️ [FONT DETECT] Error detecting fonts: {e}", flush=True)
    return ""


def _convert_legacy_text(text: str, font_name: str) -> str:
    """
    Convert legacy Malayalam ASCII text to proper Unicode using Payyans.
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
    Extract text from a PDF or TXT file using fast native PyMuPDF stream parsing.
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
                text = page.get_text("text").strip()
                
                # Check for legacy font
                detected_font = _detect_legacy_font(page, text)
                
                if detected_font and text:
                    text = _convert_legacy_text(text, detected_font)
                    if i <= 3 or i % 50 == 0:
                        preview = text[:80].replace('\n', ' ')
                        print(f"📝 [FONT CONVERT] Page {i}/{page_count}: {preview}...", flush=True)
                
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
