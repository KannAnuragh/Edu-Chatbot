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
                    print(f"⚠️ [Extractor] Legacy FML gibberish detected on page {i}. Routing through Payyans converter...", flush=True)
                    try:
                        from libindic.payyans import Payyans
                        payyans_converter = Payyans()
                        
                        # Apply Payyans to convert the garbled FML ASCII back to pristine Unicode
                        converted_text = ""
                        try:
                            converted_text = payyans_converter.ASCII2Unicode(raw_text, "ML-TTKarthika")
                        except Exception as main_e:
                            print(f"⚠️ [Extractor] ML-TTKarthika failed: {main_e}. Trying other maps...", flush=True)
                            for m in payyans_converter.listAvailableMaps():
                                try:
                                    out_text = payyans_converter.ASCII2Unicode(raw_text, m)
                                    if out_text and out_text.strip() and out_text != raw_text:
                                        converted_text = out_text
                                        print(f"⚠️ [Extractor] Success with map {m}", flush=True)
                                        break
                                except:
                                    continue
                        
                        if converted_text and converted_text.strip() and converted_text.strip() != raw_text.strip():
                            # Clean up known minor glitches from Payyans legacy mapping
                            text = converted_text.strip()
                            text = text.replace('‰', 'റ്റ').replace('‖', 'പ്പ').replace('ÿ', 'സ്ഥ')
                        else:
                            text = raw_text.strip()
                    except ImportError:
                        print("⚠️ [Extractor] libindic-payyans not installed. Falling back to raw text.", flush=True)
                        text = raw_text.strip()
                    except Exception as e:
                        print(f"⚠️ [Extractor] Payyans conversion failed for page {i}: {e}. Falling back to raw text.", flush=True)
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

