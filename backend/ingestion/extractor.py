"""
PDF and TXT Text Extractor.

Extracts text from files using PyMuPDF for PDFs and standard I/O for TXT.
Automatically converts legacy Malayalam fonts (ML-TT*) to proper Unicode
using the libindic-payyans library — completely offline, zero API tokens.
"""

from typing import List, Tuple
import pdfplumber
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


def _detect_legacy_font_heuristic(text: str) -> str:
    """
    Detect if extracted text uses a legacy Malayalam font based on content heuristics.
    """
    if not text:
        return ""
    try:
        # These specific extended ASCII characters are the hallmarks of FML/ML legacy fonts
        signature_chars = {'∂', 'Ø', '¬', '®', '¿', 'ƒ', 'Ω', '°', 'ÿ', '‰', '≥', '≤', '≠', '≈', '∆', '…'}
        char_count = sum(1 for c in text if c in signature_chars)
        
        # If we see even a few of these characters, it's a legacy Malayalam font
        if char_count > 3:
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
            # Handle PDF files using pdfplumber
            with pdfplumber.open(file_path) as doc:
                page_count = len(doc.pages)
                
                for i, page in enumerate(doc.pages, 1):
                    # Extract text using pdfplumber to better preserve complex layouts and tables
                    text = page.extract_text()
                    
                    if text:
                        text = text.strip()
                        # Check for legacy font heuristically on this extracted text
                        detected_font = _detect_legacy_font_heuristic(text)
                        
                        # If legacy font detected, convert the extracted text
                        if detected_font:
                            text = _convert_legacy_text(text, detected_font)
                            if i <= 3 or i % 50 == 0:
                                # Log progress for first few pages and every 50th page
                                preview = text[:80].replace('\n', ' ')
                                print(f"📝 [FONT CONVERT] Page {i}/{page_count}: {preview}...", flush=True)
                        
                        text = text.replace('\x00', '')  # Remove null bytes
                        pages_text.append((i, text))
                        
            return pages_text, page_count
            
    except Exception as e:
        print(f"Extraction error for {file_path}: {e}")
        raise e
    finally:
        import gc
        gc.collect()
