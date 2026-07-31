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
                    # Render page as image (zoom=1.2 balances quality and image size/network upload speed)
                    zoom = 1.2
                    mat = fitz.Matrix(zoom, zoom)
                    pix = page.get_pixmap(matrix=mat)
                    
                    # Get PNG bytes
                    img_data = pix.tobytes("png")
                    
                    # Respect rate limits for Gemini free tier (15 requests per minute -> ~4.5 seconds per request)
                    # This prevents 429 rate limit errors for large 400-700 page documents
                    import time
                    if i > 1:
                        time.sleep(4.5)
                    
                    # Initialize Gemini client
                    import os
                    from google import genai
                    from google.genai import types
                    
                    api_key = os.environ.get("GEMINI_API_KEY") or settings.GEMINI_API_KEY or ""
                    if not api_key:
                        raise ValueError("GEMINI_API_KEY is not configured. Please set it in your Render Env Vars.")
                    
                    client = genai.Client(api_key=api_key.strip())
                    
                    print(f"👁️ [GEMINI OCR] Processing page {i}/{page_count}...", flush=True)
                    
                    # Call Gemini 2.0 Flash Vision
                    response = client.models.generate_content(
                        model='gemini-2.0-flash',
                        contents=[
                            types.Part.from_bytes(
                                data=img_data,
                                mime_type="image/png"
                            ),
                            "Extract all Malayalam and English text from this image. Return only the extracted text, preserving the reading order. Do not write any intro or outro text."
                        ]
                    )
                    
                    text = response.text.strip()
                    
                    # Explicit cleanup
                    del pix, img_data
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
