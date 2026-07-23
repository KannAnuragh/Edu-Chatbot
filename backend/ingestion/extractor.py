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
                
            # 2. Fallback to OCR if page is empty or FORCE_OCR is True
            # We assume it's a scanned PDF if we get less than 50 chars of text
            if len(text) < 50 or settings.FORCE_OCR:
                try:
                    # Render page as image (zoom=2 for better OCR quality)
                    zoom = 2.0
                    mat = fitz.Matrix(zoom, zoom)
                    pix = page.get_pixmap(matrix=mat)
                    
                    # Convert to PIL Image
                    img_data = pix.tobytes("png")
                    img = Image.open(io.BytesIO(img_data))
                    
                    # Run OCR
                    ocr_text = pytesseract.image_to_string(
                        img, 
                        lang=settings.OCR_LANGUAGES
                    )
                    text = ocr_text.strip()
                    
                    # Explicit cleanup
                    img.close()
                    del img, img_data, pix
                except Exception as ocr_err:
                    print(f"OCR failed for {file_path} page {i}: {ocr_err}")
            
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
