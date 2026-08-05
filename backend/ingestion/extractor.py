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
from ingestion.font_mapper import get_dynamic_font_map

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
                
                # Check for legacy fonts on this page
                legacy_fonts_map = {}
                for font in page.get_fonts():
                    xref = font[0]
                    basefont = str(font[3]).lower() if len(font) > 3 and font[3] else ""
                    name = str(font[4]) if len(font) > 4 and font[4] else ""
                    
                    legacy_keywords = ['fml', 'ml-', 'karthika', 'matweb', 'revathi', 'thoolika', 'aymani', 'keli']
                    is_legacy = any(kw in basefont or kw in name.lower() for kw in legacy_keywords)
                    
                    if not is_legacy and has_legacy_gibberish:
                        # If gibberish is present, aggressively flag non-standard embedded fonts
                        standard_fonts = ['times', 'helv', 'arial', 'courier', 'symbol', 'zapf']
                        if not any(sf in basefont for sf in standard_fonts):
                            is_legacy = True
                            print(f"⚠️ [Extractor] Aggressively flagging '{name}' ({basefont}) as legacy due to text gibberish.", flush=True)

                    if is_legacy:
                        if xref not in doc_font_maps:
                            print(f"⚠️ [Extractor] Legacy font '{name}' ({basefont}) detected on page {i}. Generating dynamic map...", flush=True)
                            doc_font_maps[xref] = get_dynamic_font_map(doc, xref)
                        
                        # Only use the map if it actually successfully generated mappings
                        if doc_font_maps[xref]:
                            legacy_fonts_map[name] = doc_font_maps[xref]

                if not legacy_fonts_map:
                    text = raw_text.strip()
                else:
                    # Apply dynamic font maps by reading raw character data
                    text_blocks = []
                    page_dict = page.get_text("dict")
                    for block in page_dict.get("blocks", []):
                        if block.get("type") == 0:  # Text block
                            for line in block.get("lines", []):
                                line_text = ""
                                for span in line.get("spans", []):
                                    span_font = span.get("font")
                                    font_map = legacy_fonts_map.get(span_font)
                                    
                                    for char in span.get("chars", []):
                                        c = char.get("c", "")
                                        # Apply mapping if available, else use original char
                                        if font_map and c in font_map:
                                            line_text += font_map[c]
                                        else:
                                            line_text += c
                                text_blocks.append(line_text)
                    text = "\n".join(text_blocks).strip()
                
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

