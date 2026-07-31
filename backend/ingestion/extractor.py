"""
PDF Text Extractor.

Extracts text from PDF files using PyMuPDF, with optional fallback to Tesseract OCR.
"""

from typing import List, Tuple
import fitz  # PyMuPDF
import pytesseract
from PIL import Image
import io

from core.config import settings

def extract_text_from_pdf(file_path: str) -> Tuple[List[Tuple[int, str]], int]:
    """
    Extract text from a PDF file.
    
    Args:
        file_path: Path to the PDF file
        
    Returns:
        Tuple containing:
        - List of (page_number, extracted_text)
        - Total page count
    """
    pages_text = []
    
    try:
        doc = fitz.open(file_path)
        page_count = len(doc)
        
        for i, page in enumerate(doc, 1):
            text = ""
            
            # 1. Try standard text extraction
            if not settings.FORCE_OCR:
                text = page.get_text("text").strip()
                
            # 2. Only run OCR if explicitly forced in settings
            if settings.FORCE_OCR:
                try:
                    # Optimize zoom to 1.0 (maximum speed for Render free tier, slight accuracy tradeoff)
                    zoom = 1.0
                    mat = fitz.Matrix(zoom, zoom)
                    pix = page.get_pixmap(matrix=mat)
                    
                    # Convert to PIL Image
                    img_data = pix.tobytes("png")
                    img = Image.open(io.BytesIO(img_data))
                    
                    # Run OCR
                    print(f"👁️ [OCR] Processing page {i}/{page_count}...", flush=True)
                    ocr_text = pytesseract.image_to_string(
                        img, 
                        lang=settings.OCR_LANGUAGES
                    )
                    text = ocr_text.strip()
                    
                    # Explicit cleanup
                    img.close()
                    del img, img_data, pix
                except Exception as ocr_err:
                    print(f"❌ OCR failed for {file_path} page {i}: {ocr_err}", flush=True)
            
            # Only add pages that actually have text
            if text:
                # Basic cleaning
                text = text.replace('\x00', '')  # Remove null bytes
                pages_text.append((i, text))
                
        return pages_text, page_count
        
    except Exception as e:
        print(f"PDF Extraction error for {file_path}: {e}")
        raise e
    finally:
        if 'doc' in locals() and hasattr(doc, 'close'):
            doc.close()
        
        # Explicit garbage collection to free up memory from PDF chunks
        import gc
        gc.collect()
