"""
PDF and TXT Text Extractor.

Extracts text from files using PyMuPDF (fitz) for fast extraction.
Intelligently detects legacy non-Unicode Indic fonts (like FML/ML-TT),
dynamically generates a glyph-to-Unicode mapping dictionary based on visual rendering,
and seamlessly applies it during extraction.
"""

from typing import List, Tuple
import fitz  # PyMuPDF
import os
import gc

from core.config import settings

def extract_text_from_file(file_path: str) -> Tuple[List[Tuple[int, str]], int]:
    """
    Extract text from a PDF or TXT file using PyMuPDF.
    Automatically applies dynamic visual glyph mapping to legacy fonts.
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
            
            # Cache font maps during document extraction to avoid redundant disk/extraction operations
            doc_font_maps = {}
            
            for i, page in enumerate(doc, 1):
                # PRE-PASS: Check if page contains legacy gibberish (FML signatures)
                raw_text = page.get_text("text")
                import re
                has_legacy_gibberish = bool(re.search(r'[ß∂Ø∏°±ƒ]', raw_text))
                
                if has_legacy_gibberish:
                    print(f"⚠️ [Extractor] Legacy FML gibberish detected on page {i}. Routing through Payyans...", flush=True)
                    try:
                        from libindic.payyans import Payyans
                        payyans_converter = Payyans()
                        text = payyans_converter.ASCII2Unicode(raw_text, "ML-TTKarthika").strip()
                    except Exception as e:
                        print(f"⚠️ [Extractor] Payyans conversion failed for page {i}: {e}", flush=True)
                        text = raw_text.strip()
                else:
                    text = raw_text.strip()
                
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

