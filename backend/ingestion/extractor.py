"""
PDF and TXT Text Extractor.

Extracts text from files using PyMuPDF for PDFs and standard I/O for TXT.
"""

from typing import List, Tuple
import fitz  # PyMuPDF
import os

from core.config import settings

def extract_text_from_file(file_path: str) -> Tuple[List[Tuple[int, str]], int]:
    """
    Extract text from a PDF or TXT file.
    
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
            # Treat the entire text file as 1 page
            pages_text.append((1, content))
            return pages_text, 1
            
        else:
            # Handle PDF files
            doc = fitz.open(file_path)
            page_count = len(doc)
            
            for i, page in enumerate(doc, 1):
                text = page.get_text("text").strip()
                
                # Only add pages that actually have text
                if text:
                    # Basic cleaning
                    text = text.replace('\x00', '')  # Remove null bytes
                    pages_text.append((i, text))
                    
            return pages_text, page_count
            
    except Exception as e:
        print(f"Extraction error for {file_path}: {e}")
        raise e
    finally:
        if 'doc' in locals() and hasattr(doc, 'close'):
            doc.close()
        
        # Explicit garbage collection
        import gc
        gc.collect()
